"""DBOS-backed durable Worker–Reviewer trajectory runtime (apparatus 0.3.0)."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.error import URLError
from http.client import HTTPException

from dbos import DBOS, SetWorkflowID, WorkflowSerializationFormat
from jsonschema import Draft202012Validator

from ..pilot_1a.docker_executor import inspect_image
from ..pilot_1a.docker_executor import DockerExecutor
from ..pilot_1a.isolation import AgentSandbox
from ..pilot_1a.deepseek_provider import DeepSeekProvider
from ..ugs_synth_minimal.runner import (
    INITIAL_AGENT_PROMPT,
    SYSTEM_PROMPT,
    _json,
    _parse_arguments,
    _safe_arguments,
    _sha256,
    _tool_message,
    _workspace_manifest,
)
from ..ugs_synth_minimal.runtime import MinimalRuntime
from ..ugs_synth_minimal.tools import DEFAULT_MINIMAL_IMAGE, MinimalUGSSynthTools
from ..ugs_synth_minimal.tools import native_tool_definitions
from . import APPARATUS_ID as BASE_APPARATUS_ID, APPARATUS_VERSION as BASE_APPARATUS_VERSION
from .durable_store import DurableStore, canonical_json, sha256_bytes, sha256_json, utc_now
from .provider_boundary import (
    LOGGING_SCHEMA_VERSION,
    RAW_RESPONSE_CAPTURE_LEVEL,
    REDACTION_POLICY_VERSION,
    ProviderBoundaryLogger,
    _redact_value,
)
from .runner import (
    MAX_CONSECUTIVE_LENGTH_CONTINUATIONS,
    MAX_OUTPUT_TOKENS,
    MAX_PROVIDER_TOTAL_ATTEMPTS,
    MAX_PROVIDER_TRANSPORT_RETRIES,
    PROVIDER_TRANSPORT_RETRY_DELAYS_SEC,
    REVIEWER_INITIAL_PROMPT,
    REVIEWER_MAX_RESPONSES_PER_REVIEW,
    REVIEWER_MAX_TOTAL_RESPONSES,
    REVIEWER_SYSTEM_PROMPT,
    WORKER_MAX_MODEL_RESPONSES,
    WORKER_SYSTEM_PROMPT,
    _build_freeze,
    _freeze_submission,
    _git_head,
    _hash_text,
    _provider_record,
    _probe_reviewer_runtime,
    _probe_worker_runtime,
    _source_hashes,
    _tree_manifest,
    _usage_totals,
    RunInstrumentation,
    utc_now as runner_utc_now,
)
from .tools import (
    InterleavedReviewerExecutor,
    InterleavedReviewerTools,
    reviewer_tool_definitions,
    worker_tool_definitions,
)


DURABLE_APPARATUS_VERSION = "0.3.0-development"
DURABLE_RUNTIME = "DBOS"
SHORT_RETRY_DELAYS_SEC = PROVIDER_TRANSPORT_RETRY_DELAYS_SEC
LONG_BACKOFF_SECONDS = (60, 120, 300, 600, 600)
TOOL_EXECUTION_UNCERTAIN = "TOOL_EXECUTION_STATE_UNCERTAIN"
PARENT_RUN_ID = "ugs_synth_explicit_collaboration_development_001"
RESUME_RUN_ID = f"{PARENT_RUN_ID}_resume_001"
DBOS_PROCESS_CRASH_EXIT = 86


class NativeToolProvider(Protocol):
    model_id: str
    configured_model: str
    effective_model: str
    provider_name: str
    base_url: str
    thinking: str
    reasoning_effort: str
    timeout_sec: float

    def generate_with_native_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        max_output_tokens: int | None,
    ) -> Any: ...


@dataclass
class DurableRuntimeContext:
    run_root: Path
    run_id: str
    worker_provider: NativeToolProvider
    reviewer_provider: NativeToolProvider | None
    worker_tools: MinimalUGSSynthTools
    worker_sandbox: AgentSandbox
    reviewer_sandbox: AgentSandbox | None
    image: str
    store: DurableStore
    boundary_logger: "DurableProviderBoundaryLogger"
    crash_hook: Callable[[str, dict[str, Any]], None] | None = None
    image_info: dict[str, Any] | None = None
    lineage: dict[str, Any] | None = None
    reviewer_enabled: bool = True


_RUNTIME: DurableRuntimeContext | None = None


def configure_runtime(context: DurableRuntimeContext) -> None:
    global _RUNTIME
    _RUNTIME = context
    providers = [("worker", context.worker_provider)]
    if context.reviewer_enabled:
        if context.reviewer_provider is None:
            raise ValueError("reviewer_provider_required_when_reviewer_enabled")
        if context.reviewer_sandbox is None:
            raise ValueError("reviewer_sandbox_required_when_reviewer_enabled")
        providers.append(("reviewer", context.reviewer_provider))
    for actor, provider in providers:
        enable = getattr(provider, "enable_boundary_observability", None)
        if callable(enable):
            enable(context.boundary_logger, context={"run_id": context.run_id, "actor": actor})


def _ctx() -> DurableRuntimeContext:
    if _RUNTIME is None:
        raise RuntimeError("durable_runtime_context_not_configured")
    return _RUNTIME


def _tool_definitions(actor: str) -> list[dict[str, Any]]:
    if actor == "worker":
        return worker_tool_definitions_for_condition(_ctx().reviewer_enabled)
    return reviewer_tool_definitions()


def worker_tool_definitions_for_condition(reviewer_enabled: bool) -> list[dict[str, Any]]:
    """Keep the Worker-only tool surface identical to the frozen minimal baseline."""

    return worker_tool_definitions() if reviewer_enabled else native_tool_definitions()


def _conversation_messages(actor: str, through_index: int) -> list[dict[str, Any]]:
    return _ctx().store.conversation_messages(actor, through_index=through_index)


def _append_conversation(
    actor: str,
    message_id: str,
    *,
    message: dict[str, Any],
    evidence: dict[str, Any],
) -> int:
    context = _ctx()
    index = context.store.append_conversation_message(actor, message_id, message)
    context.store.append_evidence(
        f"{actor}/host_logs/messages.jsonl",
        message_id,
        evidence,
    )
    return index


def _test_crash_point(name: str, **details: Any) -> None:
    hook = _ctx().crash_hook
    if hook is not None:
        hook(name, details)


def _assert_json_state(value: Any) -> None:
    json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _is_transient_no_response_transport_error(error: BaseException) -> bool:
    details = getattr(error, "details", None)
    if not isinstance(details, dict):
        return False
    if details.get("category") != "provider_transport_error" or details.get("http_status") is not None:
        return False
    pending: list[BaseException] = [error]
    visited: set[int] = set()
    transient_types = (URLError, TimeoutError, ConnectionError, RemoteDisconnected, BrokenPipeError, OSError, HTTPException)
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if isinstance(current, transient_types):
            return True
        for nested in (current.__cause__, current.__context__):
            if isinstance(nested, BaseException):
                pending.append(nested)
        reason = getattr(current, "reason", None)
        if isinstance(reason, BaseException):
            pending.append(reason)
    return False


def _generation_record(generation: Any) -> dict[str, Any]:
    assistant = getattr(generation, "assistant_message", None)
    if not isinstance(assistant, dict):
        assistant = None
    usage = getattr(generation, "usage", {})
    if not isinstance(usage, dict):
        usage = {}
    output = {
        "assistant_message": copy.deepcopy(assistant),
        "usage": {str(key): value for key, value in usage.items() if isinstance(value, (int, float, str, bool)) or value is None},
        "returned_model": getattr(generation, "returned_model", None),
        "finish_reason": getattr(generation, "finish_reason", None),
        "latency_sec": getattr(generation, "latency_sec", None),
        "http_status": getattr(generation, "http_status", None),
    }
    _assert_json_state(output)
    return output


def _request_hash(
    provider: NativeToolProvider,
    messages: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
) -> str:
    builder = getattr(provider, "build_native_tool_request_payload", None)
    if callable(builder):
        payload = builder(messages, definitions, max_output_tokens=MAX_OUTPUT_TOKENS)
    else:
        payload = {
            "model": getattr(provider, "effective_model", getattr(provider, "model_id", None)),
            "messages": messages,
            "tools": definitions,
            "max_tokens": MAX_OUTPUT_TOKENS,
        }
    serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return sha256_bytes(serialized)


class DurableProviderBoundaryLogger(ProviderBoundaryLogger):
    """Restore provider request indexes and checkpoint parsed responses locally."""

    def __init__(self, run_root: Path, run_id: str, store: DurableStore) -> None:
        super().__init__(run_root, run_id)
        self.store = store
        existing = [self.store.boundary_state(actor) for actor in ("worker", "reviewer")]
        self._next_request_index = max((request or 0 for request, _ in existing), default=0) + 1
        for actor, (request_index, response_index) in zip(("worker", "reviewer"), existing):
            if request_index:
                self._last_request_index[actor] = request_index
            if response_index:
                self._last_response_index[actor] = response_index

    def __call__(self, event: dict[str, Any]) -> int | None:
        name = event.get("event")
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        actor = context.get("actor")
        request_id = context.get("durable_request_id")
        attempt_index = context.get("attempt_index")
        if name == "request" and isinstance(actor, str):
            reserved = self.store.reserve_boundary_request_index(actor)
            self._next_request_index = reserved
            self._last_request_index[actor] = reserved
            if isinstance(request_id, str) and isinstance(attempt_index, int):
                self.store.note_provider_request_sent(actor, request_id, attempt_index)
                self.store.append_evidence(
                    f"{actor}/host_logs/messages.jsonl",
                    f"provider-attempt:{actor}:{request_id}:{attempt_index}",
                    {
                        "kind": "provider_request_attempt",
                        "turn": context.get("turn"),
                        "review_number": context.get("review_number"),
                        "attempt": context.get("retry_index", 0) + 1,
                        "attempt_index": attempt_index,
                        "durable_request_id": request_id,
                        "request_hash": context.get("request_hash"),
                        "request_index": reserved,
                        "possible_duplicate_provider_execution": bool(context.get("possible_duplicate_provider_execution")),
                    },
                )
                _test_crash_point(
                    "provider_request_sent",
                    actor=actor,
                    turn=context.get("turn"),
                    attempt_index=attempt_index,
                    request_index=reserved,
                )
        result = super().__call__(event)
        if name == "runtime_assistant" and isinstance(actor, str) and isinstance(result, int):
            self.store.note_boundary_response(actor, result)
            if isinstance(request_id, str) and isinstance(attempt_index, int):
                secrets_value = event.get("redaction_secrets", ())
                known_secrets = tuple(value for value in secrets_value if isinstance(value, str)) if isinstance(secrets_value, (tuple, list)) else ()
                assistant = event.get("runtime_assistant_message")
                usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
                safe_assistant = _redact_value(assistant, known_secrets)
                safe_usage = _redact_value(usage, known_secrets)
                redacted = safe_assistant != assistant or safe_usage != usage
                saved = {
                    "status": "response",
                    "assistant_message": safe_assistant,
                    "usage": safe_usage,
                    "returned_model": event.get("model"),
                    "finish_reason": event.get("finish_reason"),
                    "latency_sec": None,
                    "http_status": event.get("http_status"),
                    "possible_duplicate_provider_execution": bool(context.get("possible_duplicate_provider_execution")),
                }
                self.store.save_provider_response_from_boundary(
                    actor=actor,
                    request_id=request_id,
                    attempt_index=attempt_index,
                    outcome=saved,
                    redacted=redacted,
                    possible_duplicate=bool(context.get("possible_duplicate_provider_execution")),
                )
        return result


@DBOS.step(name="durable_request_intent")
def _request_intent_step(
    actor: str,
    request_id: str,
    request_hash: str,
    turn: int,
    review_number: int | None,
    parent_unresolved_request: dict[str, Any] | None,
) -> dict[str, Any]:
    context = _ctx()
    context.store.emit_event(
        f"request:{actor}:{request_id}:prepared",
        "WORKER_REQUEST_PREPARED" if actor == "worker" else "REVIEWER_REQUEST_PREPARED",
        trajectory_id=context.run_id,
        actor=actor,
        global_worker_response=turn if actor == "worker" else None,
        global_reviewer_response=turn if actor == "reviewer" else None,
        payload={
            "durable_request_id": request_id,
            "request_hash": request_hash,
            "review_number": review_number,
            "parent_unresolved_request": parent_unresolved_request,
        },
    )
    return {"request_id": request_id, "request_hash": request_hash}


@DBOS.step(name="durable_provider_attempt_intent")
def _provider_attempt_intent_step(
    actor: str,
    request_id: str,
    logical_attempt: int,
    request_hash: str,
) -> int:
    return _ctx().store.prepare_provider_attempt(
        actor=actor,
        request_id=request_id,
        logical_attempt=logical_attempt,
        request_hash=request_hash,
    )


@DBOS.step(name="durable_provider_call")
def _provider_call_step(
    actor: str,
    request_id: str,
    request_hash: str,
    planned_attempt_index: int,
    logical_attempt: int,
    message_cursor: int,
    turn: int,
    review_number: int | None,
    parent_unresolved_request: dict[str, Any] | None,
    continuation_context: dict[str, Any] | None,
) -> dict[str, Any]:
    context = _ctx()
    ledger = context.store.begin_provider_call(actor, request_id, planned_attempt_index)
    actual_index = int(ledger["attempt_index"])
    possible_duplicate = bool(ledger.get("possible_duplicate_provider_execution")) or parent_unresolved_request is not None
    if ledger.get("outcome") is not None:
        saved = dict(ledger["outcome"])
        if saved.get("status") == "response_redacted":
            raise RuntimeError("provider_response_redacted_cannot_replay_request")
        return {
            "status": "response" if saved.get("status") == "response" else "provider_error",
            "attempt_index": actual_index,
            "request_id": request_id,
            "request_hash": request_hash,
            "retryable_transport": bool(saved.get("retryable_transport")),
            "error": saved.get("error"),
            "possible_duplicate_provider_execution": possible_duplicate,
        }
    if actor == "worker":
        provider = context.worker_provider
    elif context.reviewer_enabled and context.reviewer_provider is not None:
        provider = context.reviewer_provider
    else:
        raise RuntimeError("reviewer_provider_unavailable")
    messages = _conversation_messages(actor, message_cursor)
    definitions = _tool_definitions(actor)
    actual_request_hash = _request_hash(provider, messages, definitions)
    if actual_request_hash != request_hash:
        raise RuntimeError("durable_provider_request_hash_changed")
    set_boundary_context = getattr(provider, "set_boundary_context", None)
    if callable(set_boundary_context):
        set_boundary_context({
            "turn": turn,
            "review_number": review_number,
            "attempt_index": actual_index,
            "retry_index": logical_attempt - 1,
            "durable_request_id": request_id,
            "request_hash": request_hash,
            "possible_duplicate_provider_execution": possible_duplicate,
            "parent_unresolved_request": parent_unresolved_request,
            **(continuation_context or {}),
        })
    _test_crash_point("before_provider_call", actor=actor, turn=turn, attempt_index=actual_index)
    try:
        generation = provider.generate_with_native_tools(messages, definitions, max_output_tokens=MAX_OUTPUT_TOKENS)
    except Exception as error:
        details = getattr(error, "details", {})
        safe_error = {
            key: details[key]
            for key in ("error_type", "category", "http_status", "error_code")
            if isinstance(details, dict) and key in details
        }
        if not safe_error:
            safe_error = {"error_type": type(error).__name__, "category": "provider_error", "http_status": None}
        retryable = _is_transient_no_response_transport_error(error)
        outcome = {
            "status": "provider_error",
            "error": safe_error,
            "retryable_transport": retryable,
            "attempt_index": actual_index,
            "logical_attempt": logical_attempt,
            "request_id": request_id,
            "request_hash": request_hash,
            "possible_duplicate_provider_execution": possible_duplicate or retryable,
            "raw_response_available": safe_error.get("http_status") is not None,
        }
        context.store.record_provider_outcome(
            actor,
            request_id,
            actual_index,
            state="FAILED",
            outcome=outcome,
            raw_response_available=bool(outcome["raw_response_available"]),
            possible_duplicate=bool(outcome["possible_duplicate_provider_execution"]),
        )
        context.store.emit_event(
            f"provider-attempt:{actor}:{request_id}:{actual_index}:failed",
            "PROVIDER_ATTEMPT",
            trajectory_id=context.run_id,
            actor=actor,
            global_worker_response=turn if actor == "worker" else None,
            global_reviewer_response=turn if actor == "reviewer" else None,
            payload={**outcome, "review_number": review_number},
        )
        context.store.append_evidence(
            f"{actor}/host_logs/messages.jsonl",
            f"provider-error:{actor}:{request_id}:{actual_index}",
            {
                "kind": "provider_attempt_error",
                "turn": turn,
                "review_number": review_number,
                "attempt_index": actual_index,
                "durable_request_id": request_id,
                "request_hash": request_hash,
                "error": safe_error,
                "retryable_transport": retryable,
                "possible_duplicate_provider_execution": outcome["possible_duplicate_provider_execution"],
            },
        )
        return {
            "status": "provider_error",
            "attempt_index": actual_index,
            "request_id": request_id,
            "request_hash": request_hash,
            "retryable_transport": retryable,
            "error": safe_error,
            "possible_duplicate_provider_execution": outcome["possible_duplicate_provider_execution"],
        }

    generated = _generation_record(generation)
    returned_model = generated.get("returned_model")
    outcome = {
        "status": "response",
        **generated,
        "attempt_index": actual_index,
        "logical_attempt": logical_attempt,
        "request_id": request_id,
        "request_hash": request_hash,
        "possible_duplicate_provider_execution": possible_duplicate,
        "raw_response_available": True,
    }
    context.store.record_provider_outcome(
        actor,
        request_id,
        actual_index,
        state="SUCCEEDED",
        outcome=outcome,
        raw_response_available=True,
        possible_duplicate=possible_duplicate,
    )
    context.store.emit_event(
        f"provider-attempt:{actor}:{request_id}:{actual_index}:response",
        "PROVIDER_ATTEMPT",
        trajectory_id=context.run_id,
        actor=actor,
        global_worker_response=turn if actor == "worker" else None,
        global_reviewer_response=turn if actor == "reviewer" else None,
        payload={
            "durable_request_id": request_id,
            "request_hash": request_hash,
            "attempt_index": actual_index,
            "logical_attempt": logical_attempt,
            "review_number": review_number,
            "returned_model": returned_model,
            "raw_response_available": True,
            "possible_duplicate_provider_execution": possible_duplicate,
        },
    )
    return {
        "status": "response",
        "attempt_index": actual_index,
        "request_id": request_id,
        "request_hash": request_hash,
        "retryable_transport": False,
        "possible_duplicate_provider_execution": possible_duplicate,
    }


@DBOS.step(name="durable_provider_response_commit")
def _commit_provider_response_step(
    actor: str,
    request_id: str,
    turn: int,
    review_number: int | None,
    attempt_index: int,
) -> dict[str, Any]:
    context = _ctx()
    attempt = context.store.provider_attempt(actor, request_id, attempt_index)
    if attempt is None or attempt.get("state") != "SUCCEEDED" or not isinstance(attempt.get("outcome"), dict):
        raise RuntimeError("provider_response_not_durably_available")
    outcome = attempt["outcome"]
    generation = {key: outcome.get(key) for key in (
        "assistant_message", "usage", "returned_model", "finish_reason", "latency_sec", "http_status"
    )}
    assistant = generation.get("assistant_message")
    if not isinstance(assistant, dict) or assistant.get("role") != "assistant":
        raise RuntimeError("durable_provider_assistant_message_invalid")
    context.store.emit_event(
        f"response:{actor}:{request_id}:committed",
        "PROVIDER_RESPONSE_COMMITTED",
        trajectory_id=context.run_id,
        actor=actor,
        global_worker_response=turn if actor == "worker" else None,
        global_reviewer_response=turn if actor == "reviewer" else None,
        payload={
            "durable_request_id": request_id,
            "request_hash": outcome.get("request_hash"),
            "attempt_index": attempt_index,
            "review_number": review_number,
            "returned_model": outcome.get("returned_model"),
            "finish_reason": outcome.get("finish_reason"),
            "possible_duplicate_provider_execution": outcome.get("possible_duplicate_provider_execution", False),
            "raw_response_available": outcome.get("raw_response_available", True),
        },
    )
    _append_conversation(
        actor,
        f"model-response:{actor}:{request_id}",
        message=assistant,
        evidence={"kind": "model_response", "turn": turn, "review_number": review_number, **generation},
    )
    _test_crash_point("provider_response_committed", actor=actor, turn=turn, review_number=review_number)
    return {"status": "response_committed", "message_cursor": context.store.conversation_count(actor)}


def _provider_turn_with_recovery(
    *,
    actor: str,
    message_cursor: int,
    turn: int,
    review_number: int | None,
    prior_attempts: int = 0,
    parent_unresolved_request: dict[str, Any] | None = None,
    continuation_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one unresolved Agent turn, first with short retries, then durable waits."""

    context = _ctx()
    provider = context.worker_provider if actor == "worker" else context.reviewer_provider
    messages = _conversation_messages(actor, message_cursor)
    definitions = _tool_definitions(actor)
    request_hash = _request_hash(provider, messages, definitions)
    request_id = hashlib.sha256(
        f"{context.run_id}:{actor}:{turn}:{review_number or 0}:{request_hash}".encode("utf-8")
    ).hexdigest()
    _assert_json_state(messages)
    _assert_json_state(definitions)
    _request_intent_step(actor, request_id, request_hash, turn, review_number, parent_unresolved_request)

    logical_attempt = prior_attempts + 1
    resume_attempt_count = 0
    suspension_started_at: str | None = None
    latest_error: dict[str, Any] | None = None
    while True:
        if logical_attempt > 1 and logical_attempt <= MAX_PROVIDER_TOTAL_ATTEMPTS:
            delay = SHORT_RETRY_DELAYS_SEC[logical_attempt - 2]
            DBOS.sleep(float(delay))
            context.store.emit_event(
                f"retry-scheduled:{actor}:{request_id}:{logical_attempt}",
                "PROVIDER_RETRY_SCHEDULED",
                trajectory_id=context.run_id,
                actor=actor,
                global_worker_response=turn if actor == "worker" else None,
                global_reviewer_response=turn if actor == "reviewer" else None,
                payload={"durable_request_id": request_id, "retry_index": logical_attempt - 1, "delay_seconds": delay},
            )
        if logical_attempt <= MAX_PROVIDER_TOTAL_ATTEMPTS:
            planned_index = _provider_attempt_intent_step(actor, request_id, logical_attempt, request_hash)
            outcome = _provider_call_step(
                actor,
                request_id,
                request_hash,
                planned_index,
                logical_attempt,
                message_cursor,
                turn,
                review_number,
                parent_unresolved_request,
                continuation_context,
            )
            if outcome.get("status") == "response":
                _commit_provider_response_step(actor, request_id, turn, review_number, int(outcome["attempt_index"]))
                return {"status": "response", "attempt_index": int(outcome["attempt_index"]), "request_id": request_id, "request_hash": request_hash}
            if not outcome.get("retryable_transport"):
                return {"status": "failed", **outcome}
            latest_error = outcome.get("error") if isinstance(outcome.get("error"), dict) else None
            if logical_attempt < MAX_PROVIDER_TOTAL_ATTEMPTS:
                logical_attempt += 1
                continue

        if suspension_started_at is None:
            suspension_started_at = utc_now()
            context.store.emit_event(
                f"suspended:{actor}:{request_id}",
                "EXTERNAL_DEPENDENCY_SUSPENDED",
                trajectory_id=context.run_id,
                actor=actor,
                global_worker_response=turn if actor == "worker" else None,
                global_reviewer_response=turn if actor == "reviewer" else None,
                payload={
                    "durable_request_id": request_id,
                    "request_hash": request_hash,
                    "suspension_started_at": suspension_started_at,
                    "resume_attempt_count": 0,
                    "durable_sleep_seconds": LONG_BACKOFF_SECONDS[0],
                    "last_transport_error": latest_error,
                    "possible_duplicate_provider_execution": True,
                    "raw_response_available": False,
                },
            )
            context.store.append_evidence(
                f"{actor}/host_logs/messages.jsonl",
                f"suspended:{actor}:{request_id}",
                {
                    "kind": "external_dependency_suspended",
                    "turn": turn,
                    "review_number": review_number,
                    "durable_request_id": request_id,
                    "request_hash": request_hash,
                    "suspension_started_at": suspension_started_at,
                    "resume_attempt_count": 0,
                    "durable_sleep_seconds": LONG_BACKOFF_SECONDS[0],
                    "last_transport_error": latest_error,
                    "possible_duplicate_provider_execution": True,
                    "raw_response_available": False,
                },
            )

        long_wait = LONG_BACKOFF_SECONDS[min(resume_attempt_count, len(LONG_BACKOFF_SECONDS) - 1)]
        context.store.emit_event(
            f"durable-wait:{actor}:{request_id}:{resume_attempt_count}",
            "DURABLE_WAIT_STARTED",
            trajectory_id=context.run_id,
            actor=actor,
            global_worker_response=turn if actor == "worker" else None,
            global_reviewer_response=turn if actor == "reviewer" else None,
            payload={
                "durable_request_id": request_id,
                "suspension_started_at": suspension_started_at,
                "resume_attempt_count": resume_attempt_count,
                "durable_sleep_seconds": long_wait,
                "last_transport_error": latest_error,
            },
        )
        _test_crash_point("durable_wait_started", actor=actor, turn=turn, review_number=review_number, resume_attempt_count=resume_attempt_count)
        DBOS.sleep(float(long_wait))
        resume_attempt_count += 1
        logical_attempt += 1
        context.store.emit_event(
            f"resumed:{actor}:{request_id}:{resume_attempt_count}",
            "TRAJECTORY_RESUMED",
            trajectory_id=context.run_id,
            actor=actor,
            global_worker_response=turn if actor == "worker" else None,
            global_reviewer_response=turn if actor == "reviewer" else None,
            payload={
                "durable_request_id": request_id,
                "suspension_started_at": suspension_started_at,
                "resume_attempt_count": resume_attempt_count,
                "durable_sleep_seconds": long_wait,
                "same_unresolved_turn": True,
                "new_user_message_added": False,
            },
        )
        if actor == "worker":
            context.store.emit_event(
                f"state:worker:running-after-resume:{request_id}:{resume_attempt_count}",
                "WORKER_STATE_CHANGED",
                trajectory_id=context.run_id,
                actor="worker",
                global_worker_response=turn,
                payload={"from": "SUSPENDED_EXTERNAL_DEPENDENCY", "to": "RUNNING", "reason": "provider_retry_due"},
            )
        else:
            context.store.emit_event(
                f"state:reviewer:reviewing-after-resume:{request_id}:{resume_attempt_count}",
                "REVIEWER_STATE_CHANGED",
                trajectory_id=context.run_id,
                actor="reviewer",
                global_reviewer_response=turn,
                payload={"from": "SUSPENDED_EXTERNAL_DEPENDENCY", "to": "REVIEWING", "reason": "provider_retry_due"},
            )
        planned_index = _provider_attempt_intent_step(actor, request_id, logical_attempt, request_hash)
        outcome = _provider_call_step(
            actor,
            request_id,
            request_hash,
            planned_index,
            logical_attempt,
            message_cursor,
            turn,
            review_number,
            parent_unresolved_request,
            continuation_context,
        )
        if outcome.get("status") == "response":
            _commit_provider_response_step(actor, request_id, turn, review_number, int(outcome["attempt_index"]))
            return {"status": "response", "attempt_index": int(outcome["attempt_index"]), "request_id": request_id, "request_hash": request_hash}
        if not outcome.get("retryable_transport"):
            return {"status": "failed", **outcome}
        latest_error = outcome.get("error") if isinstance(outcome.get("error"), dict) else None
        context.store.emit_event(
            f"suspended-again:{actor}:{request_id}:{resume_attempt_count}",
            "EXTERNAL_DEPENDENCY_SUSPENDED",
            trajectory_id=context.run_id,
            actor=actor,
            global_worker_response=turn if actor == "worker" else None,
            global_reviewer_response=turn if actor == "reviewer" else None,
            payload={
                "durable_request_id": request_id,
                "request_hash": request_hash,
                "suspension_started_at": suspension_started_at,
                "resume_attempt_count": resume_attempt_count,
                "durable_sleep_seconds": LONG_BACKOFF_SECONDS[min(resume_attempt_count, len(LONG_BACKOFF_SECONDS) - 1)],
                "last_transport_error": latest_error,
                "possible_duplicate_provider_execution": True,
                "raw_response_available": False,
            },
        )


def _write_bytes_atomically(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".pending", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _record_formal_review_idempotent(
    *,
    review_root: Path,
    review_workspace: Path,
    review_number: int,
    snapshot_info: dict[str, Any],
    formal_review: dict[str, Any],
) -> str:
    review_dir = review_root / f"review_{review_number:04d}"
    review_dir.mkdir(parents=True, exist_ok=True)
    result_bytes = (json.dumps(formal_review, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    result_hash = _sha256(result_bytes)
    result_path = review_dir / "formal_review.json"
    if result_path.is_file():
        if _sha256(result_path.read_bytes()) != result_hash:
            raise RuntimeError("formal_review_commit_conflict")
    else:
        _write_bytes_atomically(result_path, result_bytes)

    history_path = review_workspace / "review_history.jsonl"
    if history_path.is_file():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            try:
                previous = json.loads(line)
            except json.JSONDecodeError:
                continue
            if previous.get("review_number") == review_number:
                if previous.get("formal_review_sha256") != result_hash:
                    raise RuntimeError("formal_review_history_conflict")
                return result_hash
    record = {
        "review_number": review_number,
        "snapshot_sha256": snapshot_info["snapshot_sha256"],
        "snapshot_manifest": snapshot_info,
        "formal_review": formal_review,
        "formal_review_sha256": result_hash,
        "completed_at": utc_now(),
    }
    history_path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    descriptor = os.open(history_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o666)
    try:
        os.write(descriptor, line)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return result_hash


def _review_snapshot_path(review_number: int) -> Path:
    return _ctx().run_root / "reviewer" / "submission_snapshots" / f"review_{review_number:04d}"


@DBOS.step(name="durable_prepare_tool_call")
def _prepare_tool_call_step(
    actor: str,
    tool_call_id: str,
    tool_name: str,
    assistant_message_index: int,
    call_index: int,
    turn: int,
    review_number: int | None,
    mutating: bool,
) -> dict[str, Any]:
    context = _ctx()
    assistant = context.store.conversation_message(actor, assistant_message_index)
    calls = assistant.get("tool_calls") if isinstance(assistant, dict) else None
    if not isinstance(calls, list) or call_index < 0 or call_index >= len(calls):
        raise RuntimeError("tool_call_source_message_missing")
    call = calls[call_index]
    function = call.get("function") if isinstance(call, dict) else None
    raw_arguments = function.get("arguments") if isinstance(function, dict) else None
    arguments, parse_error = _parse_arguments(raw_arguments)
    before = None
    if mutating:
        project_root = _tool_project_root(actor)
        before = _workspace_manifest(project_root)
    safe_arguments = _safe_arguments(tool_name, arguments) if arguments is not None else {}
    safe_arguments = safe_arguments or {}
    existing = context.store.prepare_tool(
        actor=actor,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        safe_arguments=safe_arguments,
        before_manifest=before,
        trajectory_id=context.run_id,
        global_worker_response=turn if actor == "worker" else None,
        global_reviewer_response=turn if actor == "reviewer" else None,
    )
    output = {"state": existing["state"], "parse_error": parse_error}
    _assert_json_state(output)
    return output


def _tool_arguments_from_message(
    actor: str, assistant_message_index: int, call_index: int
) -> tuple[dict[str, Any] | None, str | None]:
    assistant = _ctx().store.conversation_message(actor, assistant_message_index)
    calls = assistant.get("tool_calls") if isinstance(assistant, dict) else None
    if not isinstance(calls, list) or call_index < 0 or call_index >= len(calls):
        return None, "tool_call_source_message_missing"
    call = calls[call_index]
    function = call.get("function") if isinstance(call, dict) else None
    raw_arguments = function.get("arguments") if isinstance(function, dict) else None
    return _parse_arguments(raw_arguments)


def _append_tool_evidence(
    *,
    actor: str,
    tool_call_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    validation_status: str,
    turn: int,
    review_number: int | None,
    before_manifest: dict[str, Any] | None,
    after_manifest: dict[str, Any] | None,
) -> None:
    context = _ctx()
    message = {
        "turn": turn,
        "review_number": review_number,
        "tool_call_id": tool_call_id,
        "tool": tool_name,
        "arguments": _safe_arguments(tool_name, arguments),
        "validation_status": validation_status,
        "result": result,
    }
    context.store.append_evidence(
        f"{actor}/host_logs/tool_calls.jsonl",
        f"tool-call:{actor}:{tool_call_id}",
        message,
    )
    if before_manifest is None or after_manifest is None:
        return
    before_files = before_manifest.get("files", {})
    after_files = after_manifest.get("files", {})
    for relative in sorted(before_files.keys() | after_files.keys()):
        old = before_files.get(relative)
        new = after_files.get(relative)
        if old == new:
            continue
        row = new or old or {}
        context.store.append_evidence(
            f"{actor}/host_logs/workspace_evolution.jsonl",
            f"workspace:{actor}:{tool_call_id}:{relative}",
            {
                "turn": turn,
                "review_number": review_number,
                "tool_call_id": tool_call_id,
                "path": ("project/" if actor == "worker" else "review/") + relative.rstrip("/"),
                "action": "create" if old is None else "delete" if new is None else "modify",
                "size_bytes": row.get("size_bytes"),
                "sha256": row.get("sha256"),
            },
        )


def _tool_project_root(actor: str) -> Path:
    context = _ctx()
    if actor == "worker":
        return context.worker_sandbox.project_root
    if actor == "reviewer":
        if context.reviewer_sandbox is None:
            raise RuntimeError("reviewer_sandbox_unavailable")
        return context.reviewer_sandbox.project_root
    raise ValueError("unknown_tool_actor")


def _project_tool_result(
    *,
    actor: str,
    tool_call_id: str,
    tool_name: str,
    assistant_message_index: int,
    call_index: int,
    turn: int,
    review_number: int | None,
    validation_status: str,
    result: dict[str, Any],
) -> None:
    context = _ctx()
    arguments, _ = _tool_arguments_from_message(actor, assistant_message_index, call_index)
    arguments = arguments or {}
    committed = context.store.commit_tool(
        actor,
        tool_call_id,
        trajectory_id=context.run_id,
        global_worker_response=turn if actor == "worker" else None,
        global_reviewer_response=turn if actor == "reviewer" else None,
    )
    result = committed["result"]
    before = committed.get("before_manifest")
    after = committed.get("after_manifest")
    _append_tool_evidence(
        actor=actor,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        arguments=arguments,
        result=result,
        validation_status=validation_status,
        turn=turn,
        review_number=review_number,
        before_manifest=before,
        after_manifest=after,
    )
    message = _tool_message(tool_call_id, result)
    _append_conversation(
        actor,
        f"tool-result:{actor}:{tool_call_id}",
        message=message,
        evidence={"kind": "tool_result", "turn": turn, "review_number": review_number, **message},
    )


@DBOS.step(name="durable_execute_tool_call")
def _execute_tool_call_step(
    actor: str,
    tool_call_id: str,
    tool_name: str,
    assistant_message_index: int,
    call_index: int,
    turn: int,
    review_number: int | None,
    snapshot_root: str | None,
    snapshot_info: dict[str, Any] | None,
    validation_status: str,
    precomputed_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = _ctx()
    existing = context.store.get_tool(actor, tool_call_id)
    if existing is None:
        raise RuntimeError("tool_call_not_prepared")
    arguments, parse_error = _tool_arguments_from_message(actor, assistant_message_index, call_index)
    if arguments is None:
        arguments = {}
    if existing["state"] == "COMMITTED":
        _project_tool_result(
            actor=actor, tool_call_id=tool_call_id, tool_name=tool_name,
            assistant_message_index=assistant_message_index, call_index=call_index,
            turn=turn, review_number=review_number, validation_status=validation_status,
            result=json.loads(existing["result"]),
        )
        return {"status": "committed"}
    if existing["state"] == "SIDE_EFFECTS_OBSERVED":
        expected_after = json.loads(existing["after_manifest"]) if existing.get("after_manifest") else None
        if expected_after is not None and _workspace_manifest(_tool_project_root(actor)) != expected_after:
            reason = "observed_workspace_after_state_changed_before_tool_commit"
            context.store.mark_tool_uncertain(actor, tool_call_id, reason)
            context.store.emit_event(
                f"tool:{actor}:{tool_call_id}:uncertain",
                TOOL_EXECUTION_UNCERTAIN,
                trajectory_id=context.run_id,
                actor=actor,
                global_worker_response=turn if actor == "worker" else None,
                global_reviewer_response=turn if actor == "reviewer" else None,
                payload={"tool_call_id": tool_call_id, "tool": tool_name, "workspace_may_have_changed": True},
            )
            return {"status": "uncertain", "error": reason}
        committed = context.store.commit_tool(
            actor,
            tool_call_id,
            trajectory_id=context.run_id,
            global_worker_response=turn if actor == "worker" else None,
            global_reviewer_response=turn if actor == "reviewer" else None,
        )
        result = committed["result"]
        _project_tool_result(
            actor=actor, tool_call_id=tool_call_id, tool_name=tool_name,
            assistant_message_index=assistant_message_index, call_index=call_index,
            turn=turn, review_number=review_number, validation_status=validation_status,
            result=result,
        )
        return {"status": "committed"}
    if existing["state"] == TOOL_EXECUTION_UNCERTAIN:
        return {"status": "uncertain", "error": existing.get("error")}
    if (
        existing["state"] == "EXECUTING"
        and tool_name == "execute_python"
        and validation_status == "valid"
        and precomputed_result is None
    ):
        context.store.mark_tool_uncertain(actor, tool_call_id, "process_restarted_during_execute_python")
        context.store.emit_event(
            f"tool:{actor}:{tool_call_id}:uncertain",
            TOOL_EXECUTION_UNCERTAIN,
            trajectory_id=context.run_id,
            actor=actor,
            global_worker_response=turn if actor == "worker" else None,
            global_reviewer_response=turn if actor == "reviewer" else None,
            payload={"tool_call_id": tool_call_id, "tool": tool_name, "workspace_may_have_changed": True},
        )
        return {"status": "uncertain", "error": "process_restarted_during_execute_python"}

    before_manifest = json.loads(existing["before_manifest"]) if existing.get("before_manifest") else None
    context.store.mark_tool_executing(actor, tool_call_id)
    external_execution_started = precomputed_result is None and validation_status == "valid"
    if precomputed_result is not None:
        result = precomputed_result
    elif actor == "worker":
        try:
            result = context.worker_tools.dispatch(tool_name, arguments)
        except Exception as exc:
            result = {"error_category": "tool_runtime_error", "tool_error": type(exc).__name__}
    else:
        if review_number is None or snapshot_root is None or snapshot_info is None:
            raise RuntimeError("reviewer_tool_context_missing")
        reviewer_sandbox = context.reviewer_sandbox
        if reviewer_sandbox is None:
            raise RuntimeError("reviewer_sandbox_unavailable")
        review_number_value = review_number
        executor = InterleavedReviewerExecutor(
            image=context.image,
            brief_root=reviewer_sandbox.brief_root,
            project_root=reviewer_sandbox.project_root,
            submission_root=Path(snapshot_root),
        )
        tools = InterleavedReviewerTools(
            sandbox=reviewer_sandbox,
            executor=executor,
            review_number=review_number_value,
            snapshot_root=Path(snapshot_root),
            record_formal_review=lambda number, formal: _record_formal_review_idempotent(
                review_root=context.run_root / "reviewer" / "reviews",
                review_workspace=reviewer_sandbox.project_root,
                review_number=number,
                snapshot_info=snapshot_info,
                formal_review=formal,
            ),
        )
        try:
            result = tools.dispatch(tool_name, arguments)
        except Exception as exc:
            result = {"error_category": "tool_runtime_error", "tool_error": type(exc).__name__}

    if not isinstance(result, dict):
        result = {"error_category": "invalid_tool_result", "tool_error": "tool result must be an object"}
    if tool_name == "execute_python" and external_execution_started:
        _test_crash_point(
            "after_python_side_effect_before_observed",
            actor=actor,
            tool_call_id=tool_call_id,
            tool=tool_name,
        )
    project_root = _tool_project_root(actor)
    after_manifest = _workspace_manifest(project_root) if tool_name in {"write_file", "execute_python"} else None
    context.store.record_tool_observed(
        actor,
        tool_call_id,
        result=result,
        after_manifest=after_manifest,
    )
    committed = context.store.commit_tool(
        actor,
        tool_call_id,
        trajectory_id=context.run_id,
        global_worker_response=turn if actor == "worker" else None,
        global_reviewer_response=turn if actor == "reviewer" else None,
    )
    result = committed["result"]
    _project_tool_result(
        actor=actor, tool_call_id=tool_call_id, tool_name=tool_name,
        assistant_message_index=assistant_message_index, call_index=call_index,
        turn=turn, review_number=review_number, validation_status=validation_status,
        result=result,
    )
    _test_crash_point("tool_result_committed", actor=actor, tool_call_id=tool_call_id, tool=tool_name)
    return {"status": "committed"}


@DBOS.step(name="durable_prepare_review_snapshot")
def _prepare_review_snapshot_step(
    review_number: int,
    tool_call_id: str,
    note: str,
    turn: int,
) -> dict[str, Any]:
    context = _ctx()
    if not context.reviewer_enabled or context.reviewer_sandbox is None:
        raise RuntimeError("reviewer_context_unavailable")
    parent = context.run_root / "reviewer" / "submission_snapshots"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / f"review_{review_number:04d}"
    manifest_path = parent / f"review_{review_number:04d}_manifest.json"
    source_manifest = _tree_manifest(context.worker_sandbox.project_root)

    if target.exists() and manifest_path.is_file():
        snapshot_info = json.loads(manifest_path.read_text(encoding="utf-8"))
        if snapshot_info.get("source_project") != source_manifest or snapshot_info.get("snapshot") != _tree_manifest(target):
            raise RuntimeError("review_snapshot_recovery_conflict")
    else:
        if target.exists():
            shutil.rmtree(target)

        pending = parent / f".review_{review_number:04d}_{hashlib.sha256(tool_call_id.encode()).hexdigest()[:12]}.pending"
        if pending.exists():
            shutil.rmtree(pending)
        snapshot_info = _freeze_submission(context.worker_sandbox.project_root, pending)
        os.replace(pending, target)
        manifest_bytes = (json.dumps(snapshot_info, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        _write_bytes_atomically(manifest_path, manifest_bytes)
    context.store.append_evidence(
        "reviewer/snapshots.jsonl",
        f"snapshot:{review_number:04d}",
        {
            "review_number": review_number,
            "snapshot_path": target.relative_to(context.run_root).as_posix(),
            "snapshot_sha256": snapshot_info["snapshot_sha256"],
            "source_file_count": snapshot_info["source_project"]["file_count"],
            "snapshot_file_count": snapshot_info["snapshot"]["file_count"],
            "worker_note": note,
            "worker_response": turn,
        },
    )
    return snapshot_info


@DBOS.step(name="durable_complete_delegated_tool")
def _complete_delegated_tool_step(
    actor: str,
    tool_call_id: str,
    tool_name: str,
    assistant_message_index: int,
    call_index: int,
    result: dict[str, Any],
    turn: int,
    review_number: int,
) -> dict[str, Any]:
    context = _ctx()
    existing = context.store.get_tool(actor, tool_call_id)
    if existing is None:
        raise RuntimeError("delegated_tool_not_prepared")
    if existing["state"] == "COMMITTED":
        _project_tool_result(
            actor=actor, tool_call_id=tool_call_id, tool_name=tool_name,
            assistant_message_index=assistant_message_index, call_index=call_index,
            turn=turn, review_number=review_number, validation_status="valid",
            result=json.loads(existing["result"]),
        )
        return {"status": "committed"}
    if existing["state"] == "PREPARED":
        context.store.mark_tool_executing(actor, tool_call_id)
    context.store.record_tool_observed(actor, tool_call_id, result=result, after_manifest=None)
    _project_tool_result(
        actor=actor, tool_call_id=tool_call_id, tool_name=tool_name,
        assistant_message_index=assistant_message_index, call_index=call_index,
        turn=turn, review_number=review_number, validation_status="valid", result=result,
    )
    _test_crash_point("review_completed_before_submit_tool_commit", review_number=review_number, tool_call_id=tool_call_id)
    return {"status": "committed"}


def _review_request_text(review_number: int, note: str, snapshot_info: dict[str, Any]) -> str:
    request = {
        "review_number": review_number,
        "submission_snapshot_sha256": snapshot_info["snapshot_sha256"],
        "worker_note": note,
    }
    return (
        f"Review request {review_number}. The current submission/ is the complete read-only project snapshot made when the Worker requested this review. "
        "Review this current snapshot against the public brief. Use earlier context and review/review_history.jsonl to remember your prior findings; judge their current state yourself. "
        "Return the formal review only by calling finish_review. The Worker will receive only the review summary and formal findings.\n\n"
        f"Request details (JSON):\n{json.dumps(request, ensure_ascii=False, sort_keys=True)}"
    )


def _stored_generation(actor: str, request_id: str, attempt_index: int) -> dict[str, Any]:
    attempt = _ctx().store.provider_attempt(actor, request_id, attempt_index)
    if attempt is None or not isinstance(attempt.get("outcome"), dict):
        raise RuntimeError("provider_generation_not_found")
    return attempt["outcome"]


def _tool_result(actor: str, tool_call_id: str) -> dict[str, Any]:
    row = _ctx().store.get_tool(actor, tool_call_id)
    if row is None or not row.get("result"):
        raise RuntimeError("committed_tool_result_not_found")
    value = json.loads(row["result"])
    if not isinstance(value, dict):
        raise RuntimeError("stored_tool_result_is_not_object")
    return value


def _validate_tool_call(actor: str, name: Any, raw_arguments: Any) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None]:
    tool_name = name if isinstance(name, str) else "unknown"
    parsed, parse_error = _parse_arguments(raw_arguments)
    validation = parse_error
    result: dict[str, Any] | None = None
    definitions = _tool_definitions(actor)
    schemas = {row["function"]["name"]: row["function"]["parameters"] for row in definitions}
    if validation is None and (not isinstance(name, str) or name not in schemas):
        validation = "unknown_native_tool"
    if validation is None and parsed is not None and list(Draft202012Validator(schemas[tool_name]).iter_errors(parsed)):
        validation = "tool_schema_violation"
    if validation is not None or parsed is None:
        result = {"error_category": validation or "invalid_native_tool_arguments", "tool_error": "invalid native tool arguments"}
    return parsed, validation, result


def _emit_role_state(actor: str, state: str, *, turn: int | None = None, review_number: int | None = None, reason: str | None = None) -> None:
    context = _ctx()
    event = "WORKER_STATE_CHANGED" if actor == "worker" else "REVIEWER_STATE_CHANGED"
    context.store.emit_event(
        f"state:{actor}:{state}:{review_number if review_number is not None else 'trajectory'}:{turn if turn is not None else 0}",
        event,
        trajectory_id=context.run_id,
        actor=actor,
        global_worker_response=turn if actor == "worker" else None,
        global_reviewer_response=turn if actor == "reviewer" else None,
        payload={"to": state, "review_number": review_number, "reason": reason},
    )


@DBOS.step(name="durable_append_review_request")
def _append_review_request_step(
    review_number: int,
    note: str,
    snapshot_info: dict[str, Any],
    worker_response: int,
) -> int:
    context = _ctx()
    text = _review_request_text(review_number, note, snapshot_info)
    index = _append_conversation(
        "reviewer",
        f"review-request:{review_number:04d}",
        message={"role": "user", "content": text},
        evidence={
            "kind": "review_request",
            "review_number": review_number,
            "submission_snapshot_sha256": snapshot_info["snapshot_sha256"],
            "worker_note": note,
            "snapshot_file_count": snapshot_info["snapshot"]["file_count"],
            "worker_response": worker_response,
        },
    )
    context.store.emit_event(
        f"review-requested:{review_number:04d}",
        "REVIEW_REQUESTED",
        trajectory_id=context.run_id,
        actor="worker",
        global_worker_response=worker_response,
        payload={
            "review_number": review_number,
            "snapshot_sha256": snapshot_info["snapshot_sha256"],
            "worker_note_sha256": sha256_bytes(note.encode("utf-8")),
        },
    )
    context.store.emit_event(
        f"review-started:{review_number:04d}",
        "REVIEW_STARTED",
        trajectory_id=context.run_id,
        actor="reviewer",
        global_reviewer_response=None,
        payload={"review_number": review_number, "snapshot_sha256": snapshot_info["snapshot_sha256"]},
    )
    _emit_role_state("reviewer", "REVIEWING", review_number=review_number, reason="worker_requested_review")
    return index


def _record_invalid_tool_call(
    *, actor: str, call_id: Any, name: Any, turn: int, review_number: int | None,
    validation_status: str, call_index: int,
) -> None:
    _ctx().store.append_evidence(
        f"{actor}/host_logs/tool_calls.jsonl",
        f"invalid-tool-call:{actor}:{turn}:{review_number or 0}:{call_index}",
        {
            "turn": turn,
            "review_number": review_number,
            "tool_call_id": call_id,
            "tool": name if isinstance(name, str) else "unknown",
            "validation_status": validation_status,
        },
    )


@DBOS.workflow(name="durable_reviewer_review")
def _reviewer_workflow(
    run_id: str,
    review_number: int,
    note: str,
    snapshot_info: dict[str, Any],
    initial_message_cursor: int,
    initial_global_responses: int,
    worker_request_response: int,
) -> dict[str, Any]:
    context = _ctx()
    if context.run_id != run_id:
        raise RuntimeError("reviewer_workflow_run_id_mismatch")
    if not context.reviewer_enabled or context.reviewer_sandbox is None or context.reviewer_provider is None:
        raise RuntimeError("reviewer_context_unavailable")
    _emit_role_state("reviewer", "REVIEWING", review_number=review_number, reason="review_workflow_active")
    cursor = _append_review_request_step(review_number, note, snapshot_info, worker_request_response)
    if cursor != initial_message_cursor + 1:
        raise RuntimeError("reviewer_message_cursor_changed")

    local_responses = 0
    local_tool_calls = 0
    local_continuations = 0
    consecutive_continuations = 0
    termination = "reviewer_model_response_limit"
    formal_review: dict[str, Any] | None = None
    review_turn = 0
    for review_turn in range(1, REVIEWER_MAX_RESPONSES_PER_REVIEW + 1):
        global_response = initial_global_responses + local_responses + 1
        if global_response > REVIEWER_MAX_TOTAL_RESPONSES:
            termination = "reviewer_total_response_safety_limit"
            break
        continuation_context = None
        if consecutive_continuations:
            replayed = context.store.conversation_message("reviewer", cursor)
            continuation_context = {
                "continuation_index": consecutive_continuations,
                "triggering_response_index": context.boundary_logger.latest_response_index("reviewer"),
                "continuation_reason": "finish_reason=length with replayable content or reasoning_content",
                "assistant_message_replayed": replayed,
            }
        outcome = _provider_turn_with_recovery(
            actor="reviewer",
            message_cursor=cursor,
            turn=global_response,
            review_number=review_number,
            continuation_context=continuation_context,
        )
        if outcome.get("status") != "response":
            safe_error = outcome.get("error") if isinstance(outcome.get("error"), dict) else {"category": "provider_error"}
            context.store.append_evidence(
                "reviewer/host_logs/messages.jsonl",
                f"reviewer-provider-error:{review_number}:{review_turn}",
                {"kind": "provider_error", "review_number": review_number, "review_turn": review_turn, "error": safe_error},
            )
            termination = "reviewer_provider_error"
            break

        local_responses += 1
        cursor += 1
        generation = _stored_generation("reviewer", outcome["request_id"], int(outcome["attempt_index"]))
        assistant = generation.get("assistant_message")
        returned_model = generation.get("returned_model")
        finish_reason = generation.get("finish_reason")
        if returned_model != "deepseek-flash":
            context.store.append_evidence(
                "reviewer/host_logs/messages.jsonl",
                f"reviewer-model-mismatch:{review_number}:{review_turn}",
                {"kind": "provider_model_mismatch", "review_number": review_number, "review_turn": review_turn, "expected_model": "deepseek-flash", "returned_model": returned_model},
            )
            termination = "reviewer_model_identity_mismatch"
            break
        if not isinstance(assistant, dict) or assistant.get("role") != "assistant":
            termination = "reviewer_invalid_assistant_message"
            break
        raw_calls = assistant.get("tool_calls") or []
        if not isinstance(raw_calls, list):
            termination = "reviewer_invalid_tool_calls"
            break
        context.store.append_evidence(
            "reviewer/host_logs/messages.jsonl",
            f"reviewer-response-index:{review_number}:{review_turn}",
            {"kind": "review_response_index", "review_number": review_number, "review_turn": review_turn, "turn": global_response, "tool_call_count": len(raw_calls)},
        )
        if not raw_calls:
            if finish_reason == "length":
                has_content = any(isinstance(assistant.get(key), str) and bool(assistant[key]) for key in ("content", "reasoning_content"))
                if has_content and consecutive_continuations < MAX_CONSECUTIVE_LENGTH_CONTINUATIONS:
                    consecutive_continuations += 1
                    local_continuations += 1
                    context.store.append_evidence(
                        "reviewer/host_logs/messages.jsonl",
                        f"reviewer-length-continuation:{review_number}:{review_turn}",
                        {"kind": "length_continuation", "review_number": review_number, "review_turn": review_turn, "continuation_number": consecutive_continuations, "assistant_message_replayed": True},
                    )
                    continue
                termination = "reviewer_length_continuation_limit" if has_content else "reviewer_truncated_without_content"
            elif finish_reason == "tool_calls":
                termination = "reviewer_tool_calls_missing"
            elif finish_reason in {"content_filter", "insufficient_system_resource", "aborted"}:
                termination = f"reviewer_provider_{finish_reason}"
            else:
                termination = "reviewer_stopped_without_finish_review"
            break

        consecutive_continuations = 0
        assistant_message_index = cursor
        seen_ids: set[str] = set()
        invalid_call_id = False
        for call_index, call in enumerate(raw_calls):
            function = call.get("function") if isinstance(call, dict) else None
            name = function.get("name") if isinstance(function, dict) else None
            call_id = call.get("id") if isinstance(call, dict) else None
            raw_arguments = function.get("arguments") if isinstance(function, dict) else None
            tool_name = name if isinstance(name, str) else "unknown"
            local_tool_calls += 1
            parsed, validation, validation_result = _validate_tool_call("reviewer", name, raw_arguments)
            if not isinstance(call_id, str) or not call_id or call_id in seen_ids:
                termination = "reviewer_native_tool_call_invalid_id"
                _record_invalid_tool_call(actor="reviewer", call_id=call_id, name=name, turn=global_response, review_number=review_number, validation_status=termination, call_index=call_index)
                invalid_call_id = True
                break
            seen_ids.add(call_id)
            precomputed = {"error_category": "review_already_completed", "tool_error": "review is already complete"} if formal_review is not None else validation_result
            effective_validation = "review_already_completed" if formal_review is not None else (validation or "valid")
            _prepare_tool_call_step(
                "reviewer", call_id, tool_name, assistant_message_index, call_index,
                global_response, review_number, tool_name in {"write_file", "execute_python"},
            )
            executed = _execute_tool_call_step(
                "reviewer", call_id, tool_name, assistant_message_index, call_index,
                global_response, review_number,
                str(_review_snapshot_path(review_number)), snapshot_info,
                effective_validation, precomputed,
            )
            if executed.get("status") == "uncertain":
                termination = "reviewer_tool_execution_uncertain"
                invalid_call_id = True
                break
            result = _tool_result("reviewer", call_id)
            cursor += 1
            if tool_name == "finish_review" and result.get("status") == "finish_requested":
                review_path = context.run_root / "reviewer" / "reviews" / f"review_{review_number:04d}" / "formal_review.json"
                formal_review = json.loads(review_path.read_text(encoding="utf-8"))
                context.store.emit_event(
                    f"review-completed:{review_number:04d}",
                    "REVIEW_COMPLETED",
                    trajectory_id=run_id,
                    actor="reviewer",
                    global_reviewer_response=global_response,
                    payload={"review_number": review_number, "formal_review_sha256": result.get("formal_review_sha256"), "snapshot_sha256": snapshot_info["snapshot_sha256"]},
                )
                _emit_role_state("reviewer", "COMPLETED", turn=global_response, review_number=review_number, reason="finish_review_committed")
        if invalid_call_id:
            break
        if formal_review is not None:
            termination = "reviewer_completed"
            break
    else:
        termination = "reviewer_model_response_limit"

    messages = context.store.evidence("reviewer/host_logs/messages.jsonl")
    review_messages = [row for row in messages if row.get("review_number") == review_number]
    review_usage = [
        row.get("usage", {}) for row in review_messages
        if row.get("kind") == "model_response" and isinstance(row.get("usage"), dict)
    ]
    review_attempts = sum(
        1 for row in review_messages if row.get("kind") == "provider_request_attempt"
    )
    context.store.append_evidence(
        "reviewer/reviews.jsonl",
        f"durable-review:{review_number:04d}",
        {
            "review_number": review_number,
            "snapshot_sha256": snapshot_info["snapshot_sha256"],
            "termination_reason": termination,
            "model_responses": local_responses,
            "provider_request_attempts": review_attempts,
            "transport_retries": sum(
                1 for event in context.store.event_rows()
                if event.get("actor") == "reviewer"
                and event.get("global_reviewer_response") is not None
                and event.get("review_number") == review_number
                and event.get("event") == "PROVIDER_RETRY_SCHEDULED"
            ),
            "tool_calls": local_tool_calls,
            "token_usage": _usage_totals(review_usage),
            "token_usage_rows": review_usage,
        },
    )
    return {
        "review_number": review_number,
        "status": "completed" if formal_review is not None else "incomplete",
        "termination_reason": termination,
        "review_turns": local_responses,
        "tool_calls": local_tool_calls,
        "length_continuations": local_continuations,
        "formal_review_sha256": _sha256((context.run_root / "reviewer" / "reviews" / f"review_{review_number:04d}" / "formal_review.json").read_bytes()) if formal_review is not None else None,
        "summary": formal_review.get("summary") if formal_review is not None else None,
        "findings": formal_review.get("findings") if formal_review is not None else None,
    }


@DBOS.workflow(name="durable_worker_trajectory")
def _worker_workflow(
    run_id: str,
    initial_message_cursor: int,
    initial_global_responses: int,
    initial_review_count: int,
    initial_reviewer_global_responses: int,
    initial_length_continuations: int,
    parent_unresolved_request: dict[str, Any] | None,
) -> dict[str, Any]:
    context = _ctx()
    if context.run_id != run_id:
        raise RuntimeError("worker_workflow_run_id_mismatch")
    context.store.emit_event(
        f"trajectory-started:{run_id}",
        "TRAJECTORY_STARTED",
        trajectory_id=run_id,
        actor="worker",
        global_worker_response=initial_global_responses + 1,
        payload={"parent_run_id": (context.lineage or {}).get("parent_run_id"), "resume_segment": True},
    )
    _emit_role_state("worker", "RUNNING", turn=initial_global_responses + 1, reason="trajectory_active")
    cursor = initial_message_cursor
    response_count = initial_global_responses
    review_count = initial_review_count
    reviewer_response_count = initial_reviewer_global_responses
    total_continuations = initial_length_continuations
    consecutive_continuations = 0
    termination = "worker_model_response_limit"
    finish_requested = False
    call_counts: list[int] = []
    returned_models: list[str] = []

    while response_count < WORKER_MAX_MODEL_RESPONSES:
        turn = response_count + 1
        continuation_context = None
        if consecutive_continuations:
            continuation_context = {
                "continuation_index": consecutive_continuations,
                "triggering_response_index": context.boundary_logger.latest_response_index("worker"),
                "continuation_reason": "finish_reason=length with replayable content or reasoning_content",
                "assistant_message_replayed": context.store.conversation_message("worker", cursor),
            }
        outcome = _provider_turn_with_recovery(
            actor="worker",
            message_cursor=cursor,
            turn=turn,
            review_number=None,
            parent_unresolved_request=parent_unresolved_request if turn == initial_global_responses + 1 else None,
            continuation_context=continuation_context,
        )
        if outcome.get("status") != "response":
            safe_error = outcome.get("error") if isinstance(outcome.get("error"), dict) else {"category": "provider_error"}
            context.store.append_evidence(
                "worker/host_logs/messages.jsonl",
                f"worker-provider-error:{turn}",
                {"kind": "provider_error", "turn": turn, "error": safe_error},
            )
            termination = "worker_provider_error"
            _emit_role_state("worker", "FAILED", turn=turn, reason="non_retryable_provider_error")
            break

        response_count += 1
        cursor += 1
        generation = _stored_generation("worker", outcome["request_id"], int(outcome["attempt_index"]))
        assistant = generation.get("assistant_message")
        returned_model = generation.get("returned_model")
        finish_reason = generation.get("finish_reason")
        returned_models.append(returned_model if isinstance(returned_model, str) else "not_available")
        if returned_model != "deepseek-flash":
            termination = "worker_model_identity_mismatch"
            context.store.append_evidence(
                "worker/host_logs/messages.jsonl",
                f"worker-model-mismatch:{turn}",
                {"kind": "provider_model_mismatch", "turn": turn, "expected_model": "deepseek-flash", "returned_model": returned_model},
            )
            break
        if not isinstance(assistant, dict) or assistant.get("role") != "assistant":
            termination = "worker_invalid_assistant_message"
            context.store.append_evidence(
                "worker/host_logs/messages.jsonl",
                f"worker-invalid-assistant:{turn}",
                {"kind": "protocol_error", "turn": turn, "category": "invalid_assistant_message"},
            )
            break
        native_calls = assistant.get("tool_calls") or []
        if not isinstance(native_calls, list):
            termination = "worker_invalid_tool_calls"
            context.store.append_evidence(
                "worker/host_logs/messages.jsonl",
                f"worker-invalid-tool-calls:{turn}",
                {"kind": "protocol_error", "turn": turn, "category": "tool_calls_not_list"},
            )
            break
        if not native_calls:
            call_counts.append(0)
            if finish_reason == "length":
                has_content = any(isinstance(assistant.get(key), str) and bool(assistant[key]) for key in ("content", "reasoning_content"))
                if has_content and consecutive_continuations < MAX_CONSECUTIVE_LENGTH_CONTINUATIONS:
                    consecutive_continuations += 1
                    total_continuations += 1
                    context.store.append_evidence(
                        "worker/host_logs/messages.jsonl",
                        f"worker-length-continuation:{turn}",
                        {"kind": "length_continuation", "turn": turn, "continuation_number": consecutive_continuations, "assistant_message_replayed": True},
                    )
                    continue
                termination = "worker_length_continuation_limit" if has_content else "worker_truncated_without_content"
            elif finish_reason == "tool_calls":
                termination = "worker_tool_calls_missing"
            elif finish_reason in {"content_filter", "insufficient_system_resource", "aborted"}:
                termination = f"worker_provider_{finish_reason}"
            else:
                termination = "assistant_stopped_without_finish_project"
            break

        consecutive_continuations = 0
        call_counts.append(len(native_calls))
        assistant_message_index = cursor
        seen_ids: set[str] = set()
        invalid_call = False
        for call_index, call in enumerate(native_calls):
            function = call.get("function") if isinstance(call, dict) else None
            name = function.get("name") if isinstance(function, dict) else None
            raw_arguments = function.get("arguments") if isinstance(function, dict) else None
            call_id = call.get("id") if isinstance(call, dict) else None
            tool_name = name if isinstance(name, str) else "unknown"
            parsed, validation, validation_result = _validate_tool_call("worker", name, raw_arguments)
            if not isinstance(call_id, str) or not call_id or call_id in seen_ids:
                termination = "worker_native_tool_call_invalid_id"
                _record_invalid_tool_call(actor="worker", call_id=call_id, name=name, turn=turn, review_number=None, validation_status=termination, call_index=call_index)
                invalid_call = True
                break
            seen_ids.add(call_id)
            if finish_requested:
                validation_result = {"error_category": "project_already_finished", "tool_error": "finish_project was already accepted in this response"}
                validation = "project_already_finished"
            _prepare_tool_call_step(
                "worker", call_id, tool_name, assistant_message_index, call_index, turn, None,
                tool_name in {"write_file", "execute_python"},
            )
            if tool_name == "submit_for_review" and validation_result is None and not finish_requested:
                review_count += 1
                _emit_role_state("worker", "WAITING_FOR_REVIEW", turn=turn, review_number=review_count, reason="submit_for_review")
                snapshot_info = _prepare_review_snapshot_step(
                    review_count, call_id, parsed.get("note", "") if isinstance(parsed, dict) else "", turn,
                )
                reviewer_cursor = context.store.conversation_count("reviewer")
                reviewer_handle_id = f"{run_id}:reviewer:{review_count:04d}"
                context.store.emit_event(
                    f"review-waiting:{review_count:04d}",
                    "WORKER_STATE_CHANGED",
                    trajectory_id=run_id,
                    actor="worker",
                    global_worker_response=turn,
                    payload={"from": "RUNNING", "to": "WAITING_FOR_REVIEW", "review_number": review_count},
                )
                with SetWorkflowID(reviewer_handle_id):
                    review_handle = DBOS.start_workflow(
                        _reviewer_workflow,
                        run_id,
                        review_count,
                        parsed.get("note", "") if isinstance(parsed, dict) else "",
                        snapshot_info,
                        reviewer_cursor,
                        reviewer_response_count,
                        turn,
                    )
                review_result = review_handle.get_result(polling_interval_sec=1.0)
                reviewer_response_count += int(review_result.get("review_turns", 0))
                _test_crash_point("reviewer_completed_before_worker_receives_review", review_number=review_count, tool_call_id=call_id)
                _emit_role_state("worker", "RUNNING", turn=turn, review_number=review_count, reason="review_workflow_returned")
                if review_result.get("status") == "completed":
                    delegated_result = {
                        "review_number": review_count,
                        "summary": review_result.get("summary"),
                        "findings": review_result.get("findings"),
                    }
                else:
                    delegated_result = {
                        "review_number": review_count,
                        "status": "review_incomplete",
                        "termination_reason": review_result.get("termination_reason"),
                    }
                _complete_delegated_tool_step(
                    "worker", call_id, tool_name, assistant_message_index, call_index,
                    delegated_result, turn, review_count,
                )
                result = _tool_result("worker", call_id)
                cursor += 1
                continue

            execution = _execute_tool_call_step(
                "worker", call_id, tool_name, assistant_message_index, call_index,
                turn, None, None, None,
                validation or "valid", validation_result,
            )
            if execution.get("status") == "uncertain":
                termination = "worker_tool_execution_uncertain"
                invalid_call = True
                break
            result = _tool_result("worker", call_id)
            cursor += 1
            if tool_name == "finish_project" and result.get("status") == "finish_requested":
                finish_requested = True
                context.store.emit_event(
                    f"agent-completed:{run_id}",
                    "AGENT_COMPLETED",
                    trajectory_id=run_id,
                    actor="worker",
                    global_worker_response=turn,
                    payload={"finish_tool_call_id": call_id},
                )
        if invalid_call:
            break
        if finish_requested:
            termination = "agent_completed"
            _emit_role_state("worker", "COMPLETED", turn=turn, reason="finish_project_accepted")
            break

    return {
        "termination_reason": termination,
        "global_worker_responses": response_count,
        "worker_message_cursor": cursor,
        "review_count": review_count,
        "reviewer_global_responses": reviewer_response_count,
        "length_continuations": total_continuations,
        "finish_requested": finish_requested,
    }
