"""Prepare and run an auditable DBOS resume segment for the frozen trajectory."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from dbos import DBOS, SetWorkflowID

from ..pilot_1a.deepseek_provider import DeepSeekProvider, decode_chat_completion
from ..pilot_1a.docker_executor import DockerExecutor, inspect_image
from ..pilot_1a.isolation import AgentSandbox
from ..ugs_synth_minimal.runner import _git_head
from ..ugs_synth_minimal.tools import DEFAULT_MINIMAL_IMAGE, MinimalUGSSynthTools
from . import APPARATUS_ID, APPARATUS_VERSION as CURRENT_BASE_APPARATUS_VERSION
from .durable_runtime import (
    DURABLE_APPARATUS_VERSION,
    DurableProviderBoundaryLogger,
    DurableRuntimeContext,
    _provider_turn_with_recovery,
    _worker_workflow,
    configure_runtime,
)
from .durable_store import DurableStore, canonical_json, sha256_bytes, sha256_json, utc_now
from .provider_boundary import RAW_RESPONSE_CAPTURE_LEVEL, REDACTION_POLICY_VERSION, LOGGING_SCHEMA_VERSION
from .runner import (
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
    INITIAL_AGENT_PROMPT,
    _hash_text,
    _probe_reviewer_runtime,
    _probe_worker_runtime,
    _provider_record,
    _usage_totals,
    _workspace_manifest,
)
from .tools import reviewer_tool_definitions, worker_tool_definitions


PARENT_RUN_ID = "ugs_synth_explicit_collaboration_development_001"
RESUME_RUN_ID = f"{PARENT_RUN_ID}_resume_001"
BASE_PARENT = Path("runs/ugs_synth_interleaved_review")
RECOVERY_APPLICATION_VERSION = f"{DURABLE_APPARATUS_VERSION}-cursor-repair-001"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RuntimeError(f"jsonl_row_not_object:{path.name}")
            yield value


def _parent_paths(repo_root: Path, parent_run_id: str) -> tuple[Path, Path]:
    parent = repo_root / BASE_PARENT / parent_run_id
    return parent, parent / "artifact_hashes.json"


def verify_artifact_hashes(run_root: Path) -> dict[str, Any]:
    hash_path = run_root / "artifact_hashes.json"
    expected = json.loads(hash_path.read_text(encoding="utf-8"))
    if not isinstance(expected, dict):
        raise RuntimeError("artifact_hash_manifest_not_object")
    mismatches: list[str] = []
    for relative, value in expected.items():
        rel = PurePosixPath(relative)
        if rel.is_absolute() or ".." in rel.parts:
            mismatches.append(f"unsafe:{relative}")
            continue
        path = run_root.joinpath(*rel.parts)
        if not path.is_file():
            mismatches.append(f"missing:{relative}")
            continue
        if _sha256(path) != value:
            mismatches.append(f"hash:{relative}")
    if mismatches:
        raise RuntimeError("artifact_hash_verification_failed:" + ",".join(mismatches[:12]))
    return {
        "status": "PASS",
        "file_count": len(expected),
        "artifact_hash_manifest_sha256": _sha256(hash_path),
        "freeze_sha256": _sha256(run_root / "freeze.json"),
        "run_manifest_sha256": _sha256(run_root / "run_manifest.json"),
    }


def _artifact_hash_entries(run_root: Path) -> dict[str, str]:
    return {
        path.relative_to(run_root).as_posix(): _sha256(path)
        for path in sorted(run_root.rglob("*"))
        if path.is_file()
        and path.name != "artifact_hashes.json"
        and not path.name.endswith(("-wal", "-shm"))
    }


def _read_parent_provider_boundary(parent_root: Path) -> dict[str, Any]:
    path = parent_root / "provider_logs" / "events.jsonl"
    requests: dict[int, dict[str, Any]] = {}
    completed: set[int] = set()
    errors: dict[int, dict[str, Any]] = {}
    raw_responses: dict[int, dict[str, Any]] = {}
    last_request_by_actor: dict[str, int] = {}
    last_response_by_actor: dict[str, int] = {}
    max_request_index = 0
    target_worker: dict[str, Any] | None = None
    target_reviewer: dict[str, Any] | None = None
    target_reviewer_raw: dict[str, Any] | None = None

    for row in _jsonl(path):
        actor = row.get("actor")
        event = row.get("event")
        request_index = row.get("request_index")
        if not isinstance(actor, str) or not isinstance(request_index, int):
            continue
        if event == "request":
            compact = {
                "actor": actor,
                "request_index": request_index,
                "turn": row.get("turn"),
                "review_number": row.get("review_number"),
                "attempt_index": row.get("attempt_index"),
                "retry_index": row.get("retry_index"),
                "serialized_body_sha256": row.get("serialized_body_sha256"),
                "serialized_body_redacted": row.get("serialized_body_redacted"),
            }
            requests[request_index] = compact
            last_request_by_actor[actor] = request_index
            max_request_index = max(max_request_index, request_index)
            if actor == "worker" and row.get("turn") == 100:
                target_worker = {**compact, "serialized_body": row.get("serialized_body")}
            if actor == "reviewer" and row.get("review_number") == 1 and row.get("turn") == 60:
                target_reviewer = {**compact, "serialized_body": row.get("serialized_body")}
        elif event == "runtime_assistant":
            completed.add(request_index)
            last_response_by_actor[actor] = request_index
        elif event == "error":
            errors[request_index] = {
                "exception_type": row.get("exception_type"),
                "http_status": row.get("http_status"),
                "retry_index": row.get("retry_index"),
            }
        elif event == "response_raw" and actor == "reviewer" and request_index == last_request_by_actor.get("reviewer"):
            raw_responses[request_index] = {
                "raw_body": row.get("raw_body"),
                "raw_body_redacted": row.get("raw_body_redacted"),
                "raw_body_sha256": row.get("raw_body_sha256"),
            }

    if target_worker is None or target_reviewer is None:
        raise RuntimeError("parent_terminal_request_evidence_missing")
    worker_request_index = target_worker["request_index"]
    worker_error = errors.get(worker_request_index)
    if not worker_error or worker_error.get("exception_type") != "RemoteDisconnected" or worker_error.get("http_status") is not None:
        raise RuntimeError("parent_worker_terminal_error_is_not_expected_no_response_disconnect")
    reviewer_index = target_reviewer["request_index"]
    reviewer_raw = raw_responses.get(reviewer_index)
    if reviewer_raw is None:
        raise RuntimeError("parent_reviewer_terminal_raw_response_missing")
    return {
        "requests": requests,
        "completed": completed,
        "errors": errors,
        "last_request_by_actor": last_request_by_actor,
        "last_response_by_actor": last_response_by_actor,
        "max_request_index": max_request_index,
        "worker_terminal_request": target_worker,
        "worker_terminal_error": worker_error,
        "reviewer_terminal_request": target_reviewer,
        "reviewer_terminal_raw_response": reviewer_raw,
    }


def _logged_messages(rows: list[dict[str, Any]], actor: str, *, parent_root: Path) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if actor == "worker":
        for row in rows:
            kind = row.get("kind")
            if kind == "initial_prompt":
                messages.append({"role": row["role"], "content": row["content"]})
            elif kind == "model_response":
                messages.append(row["assistant_message"])
            elif kind == "tool_result":
                messages.append({"role": "tool", "tool_call_id": row["tool_call_id"], "content": row["content"]})
        return messages

    for row in rows:
        kind = row.get("kind")
        if kind == "initial_message":
            messages.append({"role": row["role"], "content": row["content"]})
        elif kind == "review_request":
            snapshot_manifest = parent_root / "reviewer" / "submission_snapshots" / f"review_{int(row['review_number']):04d}_manifest.json"
            snapshot_info = json.loads(snapshot_manifest.read_text(encoding="utf-8"))
            from .durable_runtime import _review_request_text
            messages.append({"role": "user", "content": _review_request_text(int(row["review_number"]), row.get("worker_note", ""), snapshot_info)})
        elif kind == "model_response":
            messages.append(row["assistant_message"])
        elif kind == "tool_result":
            messages.append({"role": "tool", "tool_call_id": row["tool_call_id"], "content": row["content"]})
    return messages


def _payload_from_boundary(row: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    body_text = row.get("serialized_body")
    if not isinstance(body_text, str) or row.get("serialized_body_redacted") is True:
        raise RuntimeError("parent_request_body_missing_or_redacted")
    body_bytes = body_text.encode("utf-8")
    if sha256_bytes(body_bytes) != row.get("serialized_body_sha256"):
        raise RuntimeError("parent_request_body_hash_mismatch")
    payload = json.loads(body_text)
    if not isinstance(payload, dict):
        raise RuntimeError("parent_request_payload_not_object")
    return payload, body_bytes


def _reconstruct_parent_messages(parent_root: Path, boundary: dict[str, Any]) -> dict[str, Any]:
    parent_manifest = json.loads((parent_root / "run_manifest.json").read_text(encoding="utf-8"))
    worker_rows = list(_jsonl(parent_root / "worker" / "host_logs" / "messages.jsonl"))
    reviewer_rows = list(_jsonl(parent_root / "reviewer" / "host_logs" / "messages.jsonl"))

    worker_payload, worker_bytes = _payload_from_boundary(boundary["worker_terminal_request"])
    worker_messages = worker_payload.get("messages")
    worker_logged = _logged_messages(worker_rows, "worker", parent_root=parent_root)
    if not isinstance(worker_messages, list) or canonical_json(worker_messages) != canonical_json(worker_logged):
        raise RuntimeError("parent_worker_message_history_does_not_match_terminal_request")
    if worker_payload.get("tools") != worker_tool_definitions():
        raise RuntimeError("parent_worker_tool_definitions_changed")
    if len([row for row in worker_rows if row.get("kind") == "model_response"]) != 99:
        raise RuntimeError("parent_worker_response_denominator_changed")

    reviewer_payload, reviewer_bytes = _payload_from_boundary(boundary["reviewer_terminal_request"])
    reviewer_messages_before = reviewer_payload.get("messages")
    if not isinstance(reviewer_messages_before, list):
        raise RuntimeError("parent_reviewer_message_history_missing")
    reviewer_raw = boundary["reviewer_terminal_raw_response"]
    if reviewer_raw.get("raw_body_redacted") is True or not isinstance(reviewer_raw.get("raw_body"), str):
        raise RuntimeError("parent_reviewer_terminal_response_redacted")
    raw_body = reviewer_raw["raw_body"].encode("utf-8")
    if sha256_bytes(raw_body) != reviewer_raw.get("raw_body_sha256"):
        raise RuntimeError("parent_reviewer_terminal_response_hash_mismatch")
    response_payload = json.loads(raw_body)
    generation = decode_chat_completion(response_payload, latency_sec=0.0, http_status=200)
    final_assistant = generation.assistant_message
    logged_last_response = next(
        row["assistant_message"] for row in reversed(reviewer_rows)
        if row.get("kind") == "model_response" and row.get("review_number") == 1 and row.get("review_turn") == 60
    )
    if final_assistant != logged_last_response:
        raise RuntimeError("parent_reviewer_response_body_does_not_match_host_log")
    reviewer_messages = list(reviewer_messages_before)
    reviewer_messages.append(final_assistant)
    final_response_position = max(
        index for index, row in enumerate(reviewer_rows)
        if row.get("kind") == "model_response" and row.get("review_number") == 1 and row.get("review_turn") == 60
    )
    final_tool_rows = [row for row in reviewer_rows[final_response_position + 1:] if row.get("kind") == "tool_result"]
    for row in final_tool_rows:
        reviewer_messages.append({"role": "tool", "tool_call_id": row["tool_call_id"], "content": row["content"]})
    reviewer_logged = _logged_messages(reviewer_rows, "reviewer", parent_root=parent_root)
    if canonical_json(reviewer_messages) != canonical_json(reviewer_logged):
        raise RuntimeError("parent_reviewer_message_history_does_not_match_terminal_evidence")
    if reviewer_payload.get("tools") != reviewer_tool_definitions():
        raise RuntimeError("parent_reviewer_tool_definitions_changed")

    worker_expected = parent_manifest.get("worker", {})
    reviewer_expected = parent_manifest.get("reviewer", {})
    if worker_expected.get("model_responses") != 99 or reviewer_expected.get("total_model_responses") != 60:
        raise RuntimeError("parent_response_counts_do_not_match_frozen_resume_boundary")
    if worker_expected.get("tool_calls") != len(list(_jsonl(parent_root / "worker" / "host_logs" / "tool_calls.jsonl"))):
        raise RuntimeError("parent_worker_tool_denominator_mismatch")
    if not worker_expected.get("finish_requested") is False:
        raise RuntimeError("parent_trajectory_already_finished")

    return {
        "worker_messages": worker_messages,
        "reviewer_messages": reviewer_messages,
        "worker_request_payload": worker_payload,
        "worker_request_bytes": worker_bytes,
        "reviewer_request_payload": reviewer_payload,
        "worker_rows": worker_rows,
        "reviewer_rows": reviewer_rows,
        "parent_manifest": parent_manifest,
        "worker_message_sha256": sha256_bytes(json.dumps(worker_messages, ensure_ascii=False).encode("utf-8")),
        "reviewer_message_sha256": sha256_bytes(json.dumps(reviewer_messages, ensure_ascii=False).encode("utf-8")),
        "worker_message_count": len(worker_messages),
        "reviewer_message_count": len(reviewer_messages),
        "worker_expected_request_sha256": boundary["worker_terminal_request"]["serialized_body_sha256"],
    }


def verify_parent_resume_boundary(repo_root: Path, parent_run_id: str = PARENT_RUN_ID) -> dict[str, Any]:
    parent_root, _ = _parent_paths(repo_root.resolve(strict=True), parent_run_id)
    if not parent_root.is_dir():
        raise FileNotFoundError("parent_run_missing")
    artifacts = verify_artifact_hashes(parent_root)
    boundary = _read_parent_provider_boundary(parent_root)
    reconstructed = _reconstruct_parent_messages(parent_root, boundary)
    return {"parent_root": parent_root, "artifacts": artifacts, "boundary": boundary, **reconstructed}


def _copy_parent_state(repo_root: Path, target_root: Path, parent_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=False)
    for actor in ("worker", "reviewer"):
        (target_root / actor).mkdir()
        shutil.copytree(parent_root / actor / "sandbox", target_root / actor / "sandbox", copy_function=shutil.copy2)
    for relative in (
        Path("reviewer") / "reviews",
        Path("reviewer") / "submission_snapshots",
    ):
        source = parent_root / relative
        if source.exists():
            shutil.copytree(source, target_root / relative, copy_function=shutil.copy2)
    public_root = repo_root / "cases" / "ugs_synth_d01" / "public"
    copied_briefs = [target_root / actor / "sandbox" / "agent_view" / "brief" for actor in ("worker", "reviewer")]
    for brief in copied_briefs:
        if not brief.is_dir() or not public_root.is_dir():
            raise RuntimeError("resume_brief_copy_missing")


def _import_parent_evidence(store: DurableStore, parent_root: Path, source: dict[str, Any], boundary: dict[str, Any]) -> None:
    for actor in ("worker", "reviewer"):
        host_root = parent_root / actor / "host_logs"
        for source_path in sorted(host_root.glob("*.jsonl")):
            sink = f"{actor}/host_logs/{source_path.name}"
            for index, row in enumerate(_jsonl(source_path), start=1):
                store.append_evidence(sink, f"parent:{source_path.stem}:{index:06d}", row)
    for relative in (Path("reviewer") / "reviews.jsonl", Path("reviewer") / "snapshots.jsonl"):
        source_path = parent_root / relative
        if source_path.is_file():
            sink = relative.as_posix()
            for index, row in enumerate(_jsonl(source_path), start=1):
                store.append_evidence(sink, f"parent:{relative.stem}:{index:06d}", row)

    for actor, messages in (("worker", source["worker_messages"]), ("reviewer", source["reviewer_messages"])):
        for index, message in enumerate(messages, start=1):
            store.append_conversation_message(actor, f"parent:{actor}:{index:06d}", message)
        if canonical_json(store.conversation_messages(actor)) != canonical_json(messages):
            raise RuntimeError(f"imported_{actor}_conversation_hash_mismatch")

    for actor in ("worker", "reviewer"):
        tool_path = parent_root / actor / "host_logs" / "tool_calls.jsonl"
        for row in _jsonl(tool_path):
            call_id = row.get("tool_call_id")
            result = row.get("result")
            if not isinstance(call_id, str) or not call_id or not isinstance(result, dict):
                continue
            arguments = row.get("arguments")
            store.import_committed_tool(
                actor=actor,
                tool_call_id=call_id,
                tool_name=row.get("tool") if isinstance(row.get("tool"), str) else "unknown",
                safe_arguments=arguments if isinstance(arguments, dict) else {},
                result=result,
                source=PARENT_RUN_ID,
            )

    attempts_by_actor = {"worker": [], "reviewer": []}
    for row in boundary["requests"].values():
        attempts_by_actor[row["actor"]].append(row)
    for actor, rows in attempts_by_actor.items():
        for attempt_index, row in enumerate(sorted(rows, key=lambda item: item["request_index"]), start=1):
            request_index = int(row["request_index"])
            has_response = request_index in boundary["completed"]
            error = boundary["errors"].get(request_index)
            request_id = f"parent:{actor}:{request_index:06d}"
            store.import_provider_attempt(
                actor=actor,
                request_id=request_id,
                attempt_index=attempt_index,
                logical_attempt=(int(row.get("retry_index") or 0) + 1),
                request_hash=str(row.get("serialized_body_sha256") or "unknown"),
                state="SUCCEEDED" if has_response else "FAILED",
                outcome={
                    "status": "parent_imported_response" if has_response else "parent_imported_error",
                    "http_status": None if not has_response else 200,
                    "error": error,
                },
                possible_duplicate=not has_response and error is not None and error.get("http_status") is None,
                raw_response_available=has_response,
            )

    for actor in ("worker", "reviewer"):
        store.seed_boundary_state(
            actor,
            last_request_index=int(boundary["last_request_by_actor"].get(actor, 0)),
            last_response_index=int(boundary["last_response_by_actor"].get(actor, 0)),
        )


def _hash_source_files(repo_root: Path) -> dict[str, str]:
    relative_files = (
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/durable_runtime.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/durable_store.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/durable_resume.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/provider_boundary.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/runner.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/tools.py",
        "src/self_organizing_engineering_agent/experiments/pilot_1a/deepseek_provider.py",
        "pyproject.toml",
        "uv.lock",
    )
    return {relative: _sha256(repo_root / relative) for relative in relative_files if (repo_root / relative).is_file()}


def _write_json(path: Path, value: dict[str, Any], *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    if exclusive:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    else:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.pending")
        try:
            with temporary.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _provider_env_file(repo_root: Path, env_file: Path | None) -> Path | None:
    """Resolve an explicit provider env file or the repository-local .env."""

    selected = env_file if env_file is not None else repo_root / ".env"
    if not selected.is_file():
        if env_file is not None:
            raise FileNotFoundError("provider_environment_file_missing")
        return None
    return selected.resolve(strict=True)


def _prepare_segment(
    repo_root: Path,
    *,
    parent_run_id: str = PARENT_RUN_ID,
    run_id: str = RESUME_RUN_ID,
    image: str | None = None,
    env_file: Path | None = None,
) -> tuple[Path, dict[str, Any], DurableRuntimeContext, DeepSeekProvider, DeepSeekProvider]:
    repo_root = repo_root.resolve(strict=True)
    verified = verify_parent_resume_boundary(repo_root, parent_run_id)
    parent_root = Path(verified["parent_root"])
    target_root = repo_root / BASE_PARENT / run_id
    if target_root.exists():
        raise FileExistsError("resume_segment_identity_already_exists")

    _copy_parent_state(repo_root, target_root, parent_root)
    runtime_root = target_root / "runtime"
    store = DurableStore(runtime_root, run_id=run_id)
    _import_parent_evidence(store, parent_root, verified, verified["boundary"])

    worker_sandbox_root = target_root / "worker" / "sandbox"
    reviewer_sandbox_root = target_root / "reviewer" / "sandbox"
    worker_sandbox = AgentSandbox(
        run_root=worker_sandbox_root.resolve(),
        agent_view=(worker_sandbox_root / "agent_view").resolve(),
        brief_root=(worker_sandbox_root / "agent_view" / "brief").resolve(),
        project_root=(worker_sandbox_root / "agent_view" / "project").resolve(),
    )
    reviewer_sandbox = AgentSandbox(
        run_root=reviewer_sandbox_root.resolve(),
        agent_view=(reviewer_sandbox_root / "agent_view").resolve(),
        brief_root=(reviewer_sandbox_root / "agent_view" / "brief").resolve(),
        project_root=(reviewer_sandbox_root / "agent_view" / "review").resolve(),
    )
    if image is None:
        parent_freeze = json.loads((parent_root / "freeze.json").read_text(encoding="utf-8"))
        image = str(parent_freeze.get("docker_image", {}).get("image", DEFAULT_MINIMAL_IMAGE))
    image_info = inspect_image(image)
    if not image_info.get("available"):
        raise RuntimeError("resume_docker_image_unavailable")
    if image_info.get("image_id") != json.loads((parent_root / "freeze.json").read_text(encoding="utf-8")).get("docker_image", {}).get("image_id"):
        raise RuntimeError("resume_docker_image_identity_changed")

    worker_executor = DockerExecutor(image=image, brief_root=worker_sandbox.brief_root, project_root=worker_sandbox.project_root)
    reviewer_probe = _probe_reviewer_runtime(reviewer_sandbox, image)
    worker_probe = _probe_worker_runtime(type("WorkerRuntime", (), {"executor": worker_executor})())
    if worker_probe.get("passed") is not True or reviewer_probe.get("passed") is not True:
        raise RuntimeError("resume_docker_isolation_probe_failed")

    parent_manifest = verified["parent_manifest"]
    if _workspace_manifest(worker_sandbox.project_root) != parent_manifest.get("worker_workspace"):
        raise RuntimeError("imported_worker_workspace_hash_mismatch")
    if _workspace_manifest(reviewer_sandbox.project_root) != parent_manifest.get("reviewer_workspace"):
        raise RuntimeError("imported_reviewer_workspace_hash_mismatch")
    provider_env = _provider_env_file(repo_root, env_file)
    worker_provider = DeepSeekProvider(env_file=provider_env)
    reviewer_provider = DeepSeekProvider(env_file=provider_env)
    if worker_provider is reviewer_provider:
        raise RuntimeError("resume_provider_instances_not_independent")
    baseline_freeze = json.loads((parent_root / "freeze.json").read_text(encoding="utf-8"))
    provider_fields = ("provider_name", "configured_model", "effective_model", "endpoint_host", "thinking", "reasoning_effort", "native_tool_calling")
    worker_record = _provider_record(worker_provider, repo_root=repo_root, definitions=worker_tool_definitions())
    reviewer_record = _provider_record(reviewer_provider, repo_root=repo_root, definitions=reviewer_tool_definitions())
    old_worker = baseline_freeze.get("worker_provider", {})
    if any(worker_record.get(key) != old_worker.get(key) for key in provider_fields if key in old_worker):
        raise RuntimeError("resume_worker_provider_configuration_changed")
    if any(reviewer_record.get(key) != old_worker.get(key) for key in provider_fields if key in old_worker):
        raise RuntimeError("resume_reviewer_provider_configuration_changed")

    exact_payload = worker_provider.build_native_tool_request_payload(
        verified["worker_messages"], worker_tool_definitions(), max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    exact_bytes = json.dumps(exact_payload, ensure_ascii=False).encode("utf-8")
    parent_body = verified["worker_request_bytes"]
    if exact_bytes != parent_body:
        raise RuntimeError("resume_first_worker_request_bytes_differ_from_parent_unresolved_request")

    from .durable_runtime import configure_runtime as _configure_runtime
    worker_tools = MinimalUGSSynthTools(worker_sandbox, worker_executor)
    boundary_logger = DurableProviderBoundaryLogger(target_root, run_id, store)
    lineage = {
        "trajectory_relationship": "resume_segment",
        "parent_run_id": parent_run_id,
        "parent_worker_responses": 99,
        "parent_review_sessions": 1,
        "resume_reason": "externally interrupted by no-response RemoteDisconnected",
        "parent_freeze_sha256": verified["artifacts"]["freeze_sha256"],
        "parent_run_manifest_sha256": verified["artifacts"]["run_manifest_sha256"],
        "parent_artifact_hash_manifest_sha256": verified["artifacts"]["artifact_hash_manifest_sha256"],
    }
    context = DurableRuntimeContext(
        run_root=target_root.resolve(),
        run_id=run_id,
        worker_provider=worker_provider,
        reviewer_provider=reviewer_provider,
        worker_tools=worker_tools,
        worker_sandbox=worker_sandbox,
        reviewer_sandbox=reviewer_sandbox,
        image=image,
        store=store,
        boundary_logger=boundary_logger,
        image_info=image_info,
        lineage=lineage,
    )
    _configure_runtime(context)

    checks = {
        "parent_artifact_hashes_verified": True,
        "parent_worker_message_hash_reconstructed": True,
        "parent_reviewer_message_hash_reconstructed": True,
        "first_worker_request_bytes_identical": True,
        "worker_workspace_hash_identical": True,
        "reviewer_workspace_hash_identical": True,
        "provider_configuration_unchanged": True,
        "provider_instances_independent": True,
        "docker_image_identity_unchanged": True,
        "worker_container_isolation_probe": worker_probe.get("passed") is True,
        "reviewer_container_isolation_probe": reviewer_probe.get("passed") is True,
        "worker_initial_response_index_is_100": verified["parent_manifest"]["worker"]["model_responses"] + 1 == 100,
        "reviewer_next_review_number_is_2": len(verified["parent_manifest"]["reviewer"].get("reviews", [])) + 1 == 2,
        "formal_state_remains_not_ready": True,
    }
    if not all(checks.values()):
        raise RuntimeError("resume_pre_run_checks_failed")

    parent_freeze = baseline_freeze
    freeze = {
        "apparatus_id": APPARATUS_ID,
        "apparatus_version": DURABLE_APPARATUS_VERSION,
        "base_apparatus_version": CURRENT_BASE_APPARATUS_VERSION,
        **lineage,
        "created_at": utc_now(),
        "git_head": _git_head(repo_root),
        "dbos": {
            "runtime": "DBOS",
            "version": importlib.metadata.version("dbos"),
            "workflow_id": f"{run_id}:worker",
            "reviewer_workflow_id_pattern": f"{run_id}:reviewer:NNNN",
            "system_database_path": "runtime/dbos.sqlite",
        },
        "durable_retry_policy": {
            "short_attempts": MAX_PROVIDER_TOTAL_ATTEMPTS,
            "short_retry_delays_sec": list(PROVIDER_TRANSPORT_RETRY_DELAYS_SEC),
            "long_backoff_seconds": [60, 120, 300, 600, 600],
            "transport_classifier": "provider_transport_error, no HTTP response, and transient exception found through cause/context/reason",
            "possible_duplicate_provider_execution": True,
        },
        "model_response_safety_limits": {
            "worker_max_global_responses": WORKER_MAX_MODEL_RESPONSES,
            "reviewer_max_responses_per_review": REVIEWER_MAX_RESPONSES_PER_REVIEW,
            "reviewer_max_global_responses": REVIEWER_MAX_TOTAL_RESPONSES,
            "max_output_tokens_per_response": MAX_OUTPUT_TOKENS,
        },
        "unchanged": [
            "worker system prompt and initial user prompt",
            "reviewer system prompt and initial user prompt",
            "Worker and Reviewer native tool definitions and schemas",
            "provider model, thinking, reasoning effort, and automatic native tool choice",
            "project brief, worker and reviewer permissions, and Docker isolation",
            "agent-facing conversation; no continuation message is injected",
        ],
        "parent_apparatus_version": parent_freeze.get("apparatus_version"),
        "parent_current_source_apparatus_version": CURRENT_BASE_APPARATUS_VERSION,
        "worker_system_prompt_sha256": _hash_text(WORKER_SYSTEM_PROMPT),
        "worker_initial_user_prompt_sha256": _hash_text(INITIAL_AGENT_PROMPT),
        "reviewer_system_prompt_sha256": _hash_text(REVIEWER_SYSTEM_PROMPT),
        "reviewer_initial_user_prompt_sha256": _hash_text(REVIEWER_INITIAL_PROMPT),
        "worker_tool_definitions_sha256": _hash_text(json.dumps(worker_tool_definitions(), ensure_ascii=False, sort_keys=True, allow_nan=False)),
        "reviewer_tool_definitions_sha256": _hash_text(json.dumps(reviewer_tool_definitions(), ensure_ascii=False, sort_keys=True, allow_nan=False)),
        "worker_provider": worker_record,
        "reviewer_provider": reviewer_record,
        "provider_instances_independent": worker_provider is not reviewer_provider,
        "docker_image": image_info,
        "runtime_source_sha256": _hash_source_files(repo_root),
        "public_world_sha256": parent_freeze.get("public_world_sha256"),
        "parent_terminal_state_import": {
            "worker_message_count": verified["worker_message_count"],
            "reviewer_message_count": verified["reviewer_message_count"],
            "worker_messages_sha256": verified["worker_message_sha256"],
            "reviewer_messages_sha256": verified["reviewer_message_sha256"],
            "worker_terminal_request_sha256": verified["worker_expected_request_sha256"],
            "worker_terminal_provider_request_index": verified["boundary"]["worker_terminal_request"]["request_index"],
            "reviewer_terminal_provider_request_index": verified["boundary"]["reviewer_terminal_request"]["request_index"],
            "worker_project_manifest_sha256": sha256_json(parent_manifest["worker_workspace"]),
            "reviewer_project_manifest_sha256": sha256_json(parent_manifest["reviewer_workspace"]),
            "reviewer_formal_review_sha256": _sha256(target_root / "reviewer" / "reviews" / "review_0001" / "formal_review.json"),
            "reviewer_snapshot_sha256": json.loads((target_root / "reviewer" / "submission_snapshots" / "review_0001_manifest.json").read_text(encoding="utf-8"))["snapshot_sha256"],
        },
        "pre_run_checks": checks,
        "container_boundary_probes": {"worker": worker_probe, "reviewer": reviewer_probe},
        "hidden_evaluator_connected": False,
        "formal_state": "UGS_FORMAL_STATE=NOT READY",
        "runtime_source_includes_parent_0_2_1_without_changing_legacy_runner": True,
        "provider_boundary_logging": "enabled",
        "logging_schema_version": LOGGING_SCHEMA_VERSION,
        "redaction_policy_version": REDACTION_POLICY_VERSION,
        "raw_response_capture_level": RAW_RESPONSE_CAPTURE_LEVEL,
        "automatic_summarization": False,
        "memory_manager": False,
        "context_reset": False,
    }
    freeze_path = target_root / "freeze.json"
    _write_json(freeze_path, freeze, exclusive=True)
    freeze_hash = _sha256(freeze_path)
    _write_json(target_root / "pre_run_checks.json", {"checks": checks, "checked_at": utc_now()}, exclusive=True)
    segment_manifest = {
        **lineage,
        "run_id": run_id,
        "apparatus_id": APPARATUS_ID,
        "apparatus_version": DURABLE_APPARATUS_VERSION,
        "segment_started_at": utc_now(),
        "status": "running",
        "termination_reason": None,
        "freeze_file": "freeze.json",
        "freeze_sha256": freeze_hash,
        "pre_run_checks": checks,
        "dbos": freeze["dbos"],
        "formal_state": "UGS_FORMAL_STATE=NOT READY",
    }
    _write_json(target_root / "run_manifest.json", segment_manifest, exclusive=True)
    return target_root, verified, context, worker_provider, reviewer_provider


def _load_segment_context(
    repo_root: Path,
    run_id: str,
    *,
    env_file: Path | None = None,
) -> tuple[Path, DurableRuntimeContext, DeepSeekProvider, DeepSeekProvider]:
    run_root = repo_root / BASE_PARENT / run_id
    segment_manifest_path = run_root / "run_manifest.json"
    freeze_path = run_root / "freeze.json"
    if not segment_manifest_path.is_file() or not freeze_path.is_file():
        raise FileNotFoundError("resume_segment_setup_is_incomplete; preserve its files and inspect")
    manifest = json.loads(segment_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("trajectory_relationship") != "resume_segment" or manifest.get("parent_run_id") != PARENT_RUN_ID:
        raise RuntimeError("resume_segment_lineage_mismatch")
    parent_root, _ = _parent_paths(repo_root, PARENT_RUN_ID)
    parent = verify_parent_resume_boundary(repo_root, PARENT_RUN_ID)
    worker_sandbox_root = run_root / "worker" / "sandbox"
    reviewer_sandbox_root = run_root / "reviewer" / "sandbox"
    worker_sandbox = AgentSandbox(
        run_root=worker_sandbox_root.resolve(), agent_view=(worker_sandbox_root / "agent_view").resolve(),
        brief_root=(worker_sandbox_root / "agent_view" / "brief").resolve(),
        project_root=(worker_sandbox_root / "agent_view" / "project").resolve(),
    )
    reviewer_sandbox = AgentSandbox(
        run_root=reviewer_sandbox_root.resolve(), agent_view=(reviewer_sandbox_root / "agent_view").resolve(),
        brief_root=(reviewer_sandbox_root / "agent_view" / "brief").resolve(),
        project_root=(reviewer_sandbox_root / "agent_view" / "review").resolve(),
    )
    runtime_root = run_root / "runtime"
    store = DurableStore(runtime_root, run_id=run_id)
    provider_env = _provider_env_file(repo_root, env_file)
    worker_provider = DeepSeekProvider(env_file=provider_env)
    reviewer_provider = DeepSeekProvider(env_file=provider_env)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    image = str(freeze.get("docker_image", {}).get("image", DEFAULT_MINIMAL_IMAGE))
    worker_executor = DockerExecutor(image=image, brief_root=worker_sandbox.brief_root, project_root=worker_sandbox.project_root)
    context = DurableRuntimeContext(
        run_root=run_root.resolve(),
        run_id=run_id,
        worker_provider=worker_provider,
        reviewer_provider=reviewer_provider,
        worker_tools=MinimalUGSSynthTools(worker_sandbox, worker_executor),
        worker_sandbox=worker_sandbox,
        reviewer_sandbox=reviewer_sandbox,
        image=image,
        store=store,
        boundary_logger=DurableProviderBoundaryLogger(run_root, run_id, store),
        image_info=freeze.get("docker_image"),
        lineage={"parent_run_id": PARENT_RUN_ID},
    )
    configure_runtime(context)
    return run_root, context, worker_provider, reviewer_provider


def _build_final_manifest(
    repo_root: Path,
    run_root: Path,
    context: DurableRuntimeContext,
    worker_result: dict[str, Any],
    *,
    started_at: str,
    workflow_was_existing: bool,
    active_worker_workflow_id: str | None = None,
    workflow_recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    store = context.store
    parent_root, _ = _parent_paths(repo_root, PARENT_RUN_ID)
    parent_manifest = json.loads((parent_root / "run_manifest.json").read_text(encoding="utf-8"))
    worker_messages = store.evidence("worker/host_logs/messages.jsonl")
    reviewer_messages = store.evidence("reviewer/host_logs/messages.jsonl")
    worker_responses = [row for row in worker_messages if row.get("kind") == "model_response"]
    reviewer_responses = [row for row in reviewer_messages if row.get("kind") == "model_response"]
    worker_usage = [row.get("usage", {}) for row in worker_responses if isinstance(row.get("usage"), dict)]
    reviewer_usage = [row.get("usage", {}) for row in reviewer_responses if isinstance(row.get("usage"), dict)]
    worker_tools = [row for row in store.tool_rows() if row["actor"] == "worker"]
    reviewer_tools = [row for row in store.tool_rows() if row["actor"] == "reviewer"]
    worker_usage_totals = _usage_totals(worker_usage)
    reviewer_usage_totals = _usage_totals(reviewer_usage)
    run_manifest_rows = store.evidence("reviewer/reviews.jsonl")
    review_rows = sorted(run_manifest_rows, key=lambda row: int(row.get("review_number", 0)))
    event_rows = store.event_rows()
    worker_termination = worker_result.get("termination_reason")
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    ended = datetime.now(timezone.utc)
    process_count = store.process_start_count()
    dbos_db = run_root / "runtime" / "dbos.sqlite"
    status = "agent_completed_without_evaluation" if worker_termination == "agent_completed" else "terminated_without_finish_project"
    manifest = {
        "apparatus_id": APPARATUS_ID,
        "apparatus_version": DURABLE_APPARATUS_VERSION,
        "base_apparatus_version": CURRENT_BASE_APPARATUS_VERSION,
        "run_id": context.run_id,
        "trajectory_relationship": "resume_segment",
        "parent_run_id": PARENT_RUN_ID,
        "parent_worker_responses": parent_manifest["worker"]["model_responses"],
        "parent_review_sessions": parent_manifest["reviewer"]["review_count"],
        "resume_reason": "externally interrupted by no-response RemoteDisconnected",
        "start_time": started_at,
        "end_time": utc_now(),
        "runtime_duration_sec": round((ended - start).total_seconds(), 3),
        "status": status,
        "termination_reason": worker_termination,
        "worker": {
            "termination_reason": worker_termination,
            "model_responses": len(worker_responses),
            "provider_request_attempts": store.provider_attempt_count("worker"),
            "transport_retries": sum(1 for row in event_rows if row.get("event") == "PROVIDER_RETRY_SCHEDULED" and row.get("actor") == "worker"),
            "tool_calls": len(worker_tools),
            "submit_for_review_calls": sum(1 for row in worker_tools if row["tool_name"] == "submit_for_review"),
            "python_executions": sum(1 for row in worker_tools if row["tool_name"] == "execute_python"),
            "calls_per_response": [len(row.get("assistant_message", {}).get("tool_calls") or []) for row in worker_responses],
            "returned_models": [row.get("returned_model") or "not_available" for row in worker_responses],
            "token_usage": worker_usage_totals,
            "token_usage_rows": worker_usage,
            "length_continuations": sum(1 for row in worker_messages if row.get("kind") == "length_continuation"),
            "finish_requested": worker_result.get("finish_requested", False),
            "review_requests": review_rows,
            "workspace": _workspace_manifest(context.worker_sandbox.project_root),
        },
        "reviewer": {
            "model_id": "deepseek-flash",
            "total_model_responses": len(reviewer_responses),
            "provider_request_attempts": store.provider_attempt_count("reviewer"),
            "total_tool_calls": len(reviewer_tools),
            "transport_retries": sum(1 for row in event_rows if row.get("event") == "PROVIDER_RETRY_SCHEDULED" and row.get("actor") == "reviewer"),
            "review_count": len(review_rows),
            "reviews": review_rows,
            "token_usage": reviewer_usage_totals,
            "token_usage_rows": reviewer_usage,
            "workspace": _workspace_manifest(context.reviewer_sandbox.project_root),
            "independent_model_context": True,
            "context_reset_between_reviews": False,
        },
        "model_id": "deepseek-flash",
        "pre_run_checks": json.loads((run_root / "pre_run_checks.json").read_text(encoding="utf-8"))["checks"],
        "hidden_evaluator_connected": False,
        "automatic_summarization": False,
        "context_reset": False,
        "persistent_worker_workspace": True,
        "persistent_reviewer_workspace": True,
        "reviewer_reasoning_returned_to_worker": False,
        "freeze_file": "freeze.json",
        "freeze_sha256": _sha256(run_root / "freeze.json"),
        "dbos": {
            "runtime": "DBOS",
            "version": importlib.metadata.version("dbos"),
            "workflow_id": active_worker_workflow_id or f"{context.run_id}:worker",
            "system_database_path": "runtime/dbos.sqlite",
            "system_database_sha256": _sha256(dbos_db) if dbos_db.is_file() else None,
            "recovery_count": max(0, process_count - 1),
            "process_restart_count": max(0, process_count - 1),
            "process_start_count": process_count,
            "workflow_was_existing_on_launcher_start": workflow_was_existing,
            "suspension_count": store.event_count("EXTERNAL_DEPENDENCY_SUSPENDED"),
            "resume_count": store.event_count("TRAJECTORY_RESUMED"),
        },
        "durable_event_count": store.event_count(),
        "durable_event_index_last": event_rows[-1]["event_index"] if event_rows else 0,
        "formal_state": "UGS_FORMAL_STATE=NOT READY",
        "setup_error": None,
    }
    if workflow_recovery is not None:
        manifest["workflow_recovery"] = workflow_recovery
    store.checkpoint()
    manifest["dbos"]["recovery_ledger_path"] = "runtime/recovery_ledger.sqlite"
    manifest["dbos"]["recovery_ledger_sha256"] = _sha256(store.path)
    _write_json(run_root / "run_manifest.json", manifest)
    artifacts = _artifact_hash_entries(run_root)
    _write_json(run_root / "artifact_hashes.json", artifacts)
    return manifest


def _sqlite_url(path: Path) -> str:
    return "sqlite:///" + path.resolve().as_posix()


def _append_recovery_event(path: Path, event: str, **fields: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"timestamp": utc_now(), "event": event, **fields}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def reconcile_final_artifact_hashes(
    repo_root: Path,
    *,
    run_id: str = RESUME_RUN_ID,
) -> dict[str, Any]:
    """Checkpoint a completed resume ledger and record a stable artifact-hash correction."""
    repo_root = repo_root.resolve(strict=True)
    run_root = repo_root / BASE_PARENT / run_id
    manifest_path = run_root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") not in {"agent_completed_without_evaluation", "terminated_without_finish_project"}:
        raise RuntimeError("artifact_reconciliation_requires_terminal_resume_segment")

    hash_path = run_root / "artifact_hashes.json"
    prior_hash_bytes = hash_path.read_bytes()
    prior_hashes = json.loads(prior_hash_bytes)
    prior_mismatches: list[str] = []
    for relative, expected in prior_hashes.items():
        rel = PurePosixPath(relative)
        if rel.is_absolute() or ".." in rel.parts:
            prior_mismatches.append(f"unsafe:{relative}")
            continue
        path = run_root.joinpath(*rel.parts)
        if not path.is_file():
            prior_mismatches.append(f"missing:{relative}")
        elif _sha256(path) != expected:
            prior_mismatches.append(f"hash:{relative}")

    reconciliation_rows = manifest.get("post_run_integrity_reconciliations", [])
    reconciliation_number = len(reconciliation_rows) + 1
    prior_snapshot = run_root / "runtime" / f"artifact_hashes_pre_reconciliation_{reconciliation_number:03d}.json"
    if not prior_snapshot.exists():
        prior_snapshot.write_bytes(prior_hash_bytes)

    recovery_ledger = run_root / "runtime" / "recovery_ledger.sqlite"
    with sqlite3.connect(recovery_ledger, timeout=30.0) as connection:
        checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    if checkpoint is not None and int(checkpoint[0]) != 0:
        raise RuntimeError("recovery_ledger_checkpoint_busy")
    ledger_hash = _sha256(recovery_ledger)
    timestamp = utc_now()
    correction = {
        "timestamp": timestamp,
        "event": "FINAL_ARTIFACT_HASH_RECONCILIATION",
        "prior_artifact_hash_manifest_sha256": sha256_bytes(prior_hash_bytes),
        "prior_artifact_hash_status": "MISMATCH" if prior_mismatches else "PASS",
        "prior_mismatches": prior_mismatches,
        "reconciliation_number": reconciliation_number,
        "checkpoint": "SQLite WAL TRUNCATE after workflow completion",
        "excluded_transient_suffixes": ["-wal", "-shm"],
        "recovery_ledger_sha256_after_checkpoint": ledger_hash,
        "source_commit": _git_head(repo_root),
        "preserved_prior_manifest": prior_snapshot.relative_to(run_root).as_posix(),
    }
    _append_recovery_event(run_root / "runtime" / "post_run_integrity.jsonl", "FINAL_ARTIFACT_HASH_RECONCILIATION", **{k: v for k, v in correction.items() if k != "event"})
    manifest["dbos"]["recovery_ledger_path"] = "runtime/recovery_ledger.sqlite"
    manifest["dbos"]["recovery_ledger_sha256"] = ledger_hash
    manifest.setdefault("post_run_integrity_reconciliations", []).append(correction)
    _write_json(manifest_path, manifest)
    _write_json(hash_path, _artifact_hash_entries(run_root))
    return {
        "run_id": run_id,
        "prior_artifact_hash_status": correction["prior_artifact_hash_status"],
        "prior_mismatches": prior_mismatches,
        "artifact_hash_verification": verify_artifact_hashes(run_root),
    }


def _assert_expected_failed_step(workflow_id: str, *, function_id: int, function_name: str) -> None:
    status = DBOS.get_workflow_status(workflow_id)
    if status is None or status.status != "ERROR" or status.app_version != DURABLE_APPARATUS_VERSION:
        raise RuntimeError(f"recovery_source_workflow_status_mismatch:{workflow_id}")
    steps = DBOS.list_workflow_steps(workflow_id)
    value = lambda row, key: row.get(key) if isinstance(row, dict) else getattr(row, key, None)
    step = next((row for row in steps if value(row, "function_id") == function_id), None)
    if step is None or value(step, "function_name") != function_name or value(step, "error") is None:
        raise RuntimeError(f"recovery_source_failed_step_mismatch:{workflow_id}:{function_id}")
    if str(value(step, "error")) != "tool_call_source_message_missing":
        raise RuntimeError(f"recovery_source_error_mismatch:{workflow_id}:{function_id}")


def _get_or_fork_workflow(
    *,
    original_workflow_id: str,
    forked_workflow_id: str,
    start_step: int,
    replacement_children: dict[str, str] | None = None,
) -> tuple[Any, bool]:
    existing = DBOS.get_workflow_status(forked_workflow_id)
    if existing is not None:
        if existing.forked_from != original_workflow_id or existing.app_version != RECOVERY_APPLICATION_VERSION:
            raise RuntimeError(f"recovery_fork_identity_mismatch:{forked_workflow_id}")
        if existing.status == "ERROR":
            raise RuntimeError(f"recovery_fork_already_failed:{forked_workflow_id}")
        return DBOS.retrieve_workflow(forked_workflow_id), False

    with SetWorkflowID(forked_workflow_id):
        handle = DBOS.fork_workflow(
            original_workflow_id,
            start_step,
            application_version=RECOVERY_APPLICATION_VERSION,
            replacement_children=replacement_children,
        )
    if handle.workflow_id != forked_workflow_id:
        raise RuntimeError(f"recovery_fork_id_assignment_failed:{forked_workflow_id}")
    return handle, True


def recover_failed_resume_segment(
    repo_root: Path,
    *,
    run_id: str = RESUME_RUN_ID,
) -> dict[str, Any]:
    """Fork the known cursor-error workflows without replaying completed provider calls."""
    repo_root = repo_root.resolve(strict=True)
    run_root = repo_root / BASE_PARENT / run_id
    manifest_path = run_root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "running" or manifest.get("trajectory_relationship") != "resume_segment":
        raise RuntimeError("recovery_requires_running_resume_segment")
    if manifest.get("parent_run_id") != PARENT_RUN_ID:
        raise RuntimeError("recovery_parent_lineage_mismatch")
    parent_root, _ = _parent_paths(repo_root, PARENT_RUN_ID)
    parent_artifact_verification = verify_artifact_hashes(parent_root)
    verify_parent_resume_boundary(repo_root, PARENT_RUN_ID)
    _, context, _, _ = _load_segment_context(repo_root, run_id)

    original_worker_id = f"{run_id}:worker"
    original_reviewer_id = f"{run_id}:reviewer:0002"
    repaired_reviewer_id = f"{original_reviewer_id}:cursor_repair_001"
    repaired_worker_id = f"{original_worker_id}:cursor_repair_001"
    recovery_journal = run_root / "runtime" / "workflow_recovery.jsonl"
    started_at = manifest.get("segment_started_at", manifest.get("start_time", utc_now()))
    worker_attempts_before = context.store.provider_attempt_count("worker")
    reviewer_attempts_before = context.store.provider_attempt_count("reviewer")
    worker_attempt_rows_before = context.store.provider_attempt_rows("worker")
    reviewer_attempt_rows_before = context.store.provider_attempt_rows("reviewer")
    worker_responses_before = context.store.evidence_count("worker/host_logs/messages.jsonl", kind="model_response")
    reviewer_responses_before = context.store.evidence_count("reviewer/host_logs/messages.jsonl", kind="model_response")
    context.store.record_process_start(f"{os.getpid()}:{uuid.uuid4()}")

    dbos_path = run_root / "runtime" / "dbos.sqlite"
    DBOS.destroy()
    DBOS(config={
        "name": "ugs_synth_interleaved_review_durable",
        "application_version": RECOVERY_APPLICATION_VERSION,
        "system_database_url": _sqlite_url(dbos_path),
    })
    DBOS.launch()
    try:
        _assert_expected_failed_step(original_reviewer_id, function_id=26, function_name="durable_prepare_tool_call")
        _assert_expected_failed_step(original_worker_id, function_id=110, function_name="DBOS.getResult")
        recovery_info = {
            "method": "DBOS.fork_workflow",
            "reason": "stable_assistant_message_index_for_multi_tool_responses",
            "application_version": RECOVERY_APPLICATION_VERSION,
            "code_commit": _git_head(repo_root),
            "source_worker_workflow_id": original_worker_id,
            "source_reviewer_workflow_id": original_reviewer_id,
            "source_worker_failed_function_id": 110,
            "source_reviewer_failed_function_id": 26,
            "reviewer_fork_workflow_id": repaired_reviewer_id,
            "worker_fork_workflow_id": repaired_worker_id,
            "worker_provider_attempts_before": worker_attempts_before,
            "reviewer_provider_attempts_before": reviewer_attempts_before,
            "worker_provider_attempts_before_sha256": sha256_json(worker_attempt_rows_before),
            "reviewer_provider_attempts_before_sha256": sha256_json(reviewer_attempt_rows_before),
            "worker_model_responses_before": worker_responses_before,
            "reviewer_model_responses_before": reviewer_responses_before,
            "parent_artifact_hash_verification": parent_artifact_verification,
        }
        _append_recovery_event(recovery_journal, "RECOVERY_FORKS_REQUESTED", **recovery_info)

        reviewer_handle, reviewer_created = _get_or_fork_workflow(
            original_workflow_id=original_reviewer_id,
            forked_workflow_id=repaired_reviewer_id,
            start_step=26,
        )
        reviewer_result = reviewer_handle.get_result(polling_interval_sec=1.0)
        reviewer_status = DBOS.get_workflow_status(repaired_reviewer_id)
        if reviewer_status is None or reviewer_status.status != "SUCCESS":
            raise RuntimeError("repaired_reviewer_workflow_did_not_succeed")
        reviewer_attempts_after = context.store.provider_attempt_count("reviewer")
        reviewer_attempt_rows_after = context.store.provider_attempt_rows("reviewer")
        if reviewer_attempt_rows_after[:len(reviewer_attempt_rows_before)] != reviewer_attempt_rows_before:
            raise RuntimeError("reviewer_fork_changed_prior_provider_attempts")
        _append_recovery_event(
            recovery_journal,
            "REVIEWER_FORK_SUCCEEDED",
            workflow_id=repaired_reviewer_id,
            source_workflow_id=original_reviewer_id,
            source_start_step=26,
            created=reviewer_created,
            reviewer_result=reviewer_result,
            reviewer_provider_attempts_after=reviewer_attempts_after,
        )

        worker_handle, worker_created = _get_or_fork_workflow(
            original_workflow_id=original_worker_id,
            forked_workflow_id=repaired_worker_id,
            start_step=110,
            replacement_children={original_reviewer_id: repaired_reviewer_id},
        )
        worker_result = worker_handle.get_result(polling_interval_sec=1.0)
        worker_attempt_rows_after = context.store.provider_attempt_rows("worker")
        if worker_attempt_rows_after[:len(worker_attempt_rows_before)] != worker_attempt_rows_before:
            raise RuntimeError("worker_fork_changed_prior_provider_attempts")
        _append_recovery_event(
            recovery_journal,
            "WORKER_FORK_FINISHED",
            workflow_id=repaired_worker_id,
            source_workflow_id=original_worker_id,
            source_start_step=110,
            replacement_children={original_reviewer_id: repaired_reviewer_id},
            created=worker_created,
            termination_reason=worker_result.get("termination_reason"),
            worker_provider_attempts_after=context.store.provider_attempt_count("worker"),
            reviewer_provider_attempts_after=context.store.provider_attempt_count("reviewer"),
        )
    except Exception as exc:
        _append_recovery_event(
            recovery_journal,
            "RECOVERY_FORK_FAILED",
            error_type=type(exc).__name__,
            error=str(exc),
            source_worker_workflow_id=original_worker_id,
            source_reviewer_workflow_id=original_reviewer_id,
            reviewer_fork_workflow_id=repaired_reviewer_id,
            worker_fork_workflow_id=repaired_worker_id,
        )
        raise
    finally:
        DBOS.destroy()

    manifest_result = _build_final_manifest(
        repo_root,
        run_root,
        context,
        worker_result,
        started_at=started_at,
        workflow_was_existing=not worker_created,
        active_worker_workflow_id=repaired_worker_id,
        workflow_recovery={
            **recovery_info,
            "reviewer_fork_created_by_this_process": reviewer_created,
            "worker_fork_created_by_this_process": worker_created,
            "reviewer_result_status": reviewer_result.get("status"),
            "reviewer_provider_attempts_after": reviewer_attempts_after,
            "worker_provider_attempts_after": context.store.provider_attempt_count("worker"),
            "journal_path": "runtime/workflow_recovery.jsonl",
            "journal_sha256": _sha256(recovery_journal),
        },
    )
    return {
        "status": manifest_result["status"],
        "run_id": run_id,
        "run_root": run_root.as_posix(),
        "termination_reason": manifest_result["termination_reason"],
        "worker_model_responses": manifest_result["worker"]["model_responses"],
        "reviewer_model_responses": manifest_result["reviewer"]["total_model_responses"],
        "review_count": manifest_result["reviewer"]["review_count"],
        "artifact_hash_verification": verify_artifact_hashes(run_root),
    }


def run_resume_segment(
    repo_root: Path,
    *,
    run_id: str = RESUME_RUN_ID,
    parent_run_id: str = PARENT_RUN_ID,
    env_file: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve(strict=True)
    run_root = repo_root / BASE_PARENT / run_id
    if run_root.exists():
        final_manifest_path = run_root / "run_manifest.json"
        if final_manifest_path.is_file():
            existing_manifest = json.loads(final_manifest_path.read_text(encoding="utf-8"))
            if existing_manifest.get("status") != "running":
                return {
                    "status": existing_manifest.get("status"),
                    "run_id": run_id,
                    "run_root": run_root.as_posix(),
                    "termination_reason": existing_manifest.get("termination_reason"),
                    "worker_model_responses": existing_manifest.get("worker", {}).get("model_responses"),
                    "reviewer_model_responses": existing_manifest.get("reviewer", {}).get("total_model_responses"),
                    "review_count": existing_manifest.get("reviewer", {}).get("review_count"),
                    "artifact_hash_verification": verify_artifact_hashes(run_root),
                }
        run_root, context, worker_provider, reviewer_provider = _load_segment_context(
            repo_root, run_id, env_file=env_file,
        )
        manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
        started_at = manifest.get("segment_started_at", manifest.get("start_time", utc_now()))
        verification = verify_parent_resume_boundary(repo_root, parent_run_id)
        cursor = context.store.conversation_count("worker")
        worker_responses = context.store.evidence_count("worker/host_logs/messages.jsonl", kind="model_response")
        reviewer_responses = context.store.evidence_count("reviewer/host_logs/messages.jsonl", kind="model_response")
        review_count = len(context.store.evidence("reviewer/reviews.jsonl"))
        continuation_count = context.store.evidence_count("worker/host_logs/messages.jsonl", kind="length_continuation")
        worker_workflow_id = f"{run_id}:worker"
        workflow_was_existing = False
    else:
        run_root, verification, context, worker_provider, reviewer_provider = _prepare_segment(
            repo_root, parent_run_id=parent_run_id, run_id=run_id, env_file=env_file,
        )
        started_at = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))["segment_started_at"]
        cursor = context.store.conversation_count("worker")
        worker_responses = context.store.evidence_count("worker/host_logs/messages.jsonl", kind="model_response")
        reviewer_responses = context.store.evidence_count("reviewer/host_logs/messages.jsonl", kind="model_response")
        review_count = len(context.store.evidence("reviewer/reviews.jsonl"))
        continuation_count = context.store.evidence_count("worker/host_logs/messages.jsonl", kind="length_continuation")
        worker_workflow_id = f"{run_id}:worker"
        workflow_was_existing = False

    if worker_responses != 99 or reviewer_responses != 60 or review_count != 1:
        raise RuntimeError("resume_import_counts_changed_before_workflow_start")
    freeze = json.loads((run_root / "freeze.json").read_text(encoding="utf-8"))
    expected_first_request_hash = freeze["parent_terminal_state_import"]["worker_terminal_request_sha256"]
    first_messages = context.store.conversation_messages("worker", through_index=cursor)
    first_payload = worker_provider.build_native_tool_request_payload(first_messages, worker_tool_definitions(), max_output_tokens=MAX_OUTPUT_TOKENS)
    first_bytes = json.dumps(first_payload, ensure_ascii=False).encode("utf-8")
    if sha256_bytes(first_bytes) != expected_first_request_hash:
        raise RuntimeError("worker_turn_100_request_hash_changed_after_import")

    session_id = f"{os.getpid()}:{uuid.uuid4()}"
    context.store.record_process_start(session_id)
    dbos_path = run_root / "runtime" / "dbos.sqlite"
    DBOS.destroy()
    DBOS(config={
        "name": "ugs_synth_interleaved_review_durable",
        "application_version": DURABLE_APPARATUS_VERSION,
        "system_database_url": _sqlite_url(dbos_path),
    })
    DBOS.launch()
    try:
        status = DBOS.get_workflow_status(worker_workflow_id)
        workflow_was_existing = status is not None
        if status is None:
            parent_manifest = verification["parent_manifest"]
            terminal_request = verification["boundary"]["worker_terminal_request"]
            unresolved = {
                "parent_run_id": parent_run_id,
                "parent_request_index": terminal_request["request_index"],
                "parent_turn": 100,
                "parent_request_sha256": terminal_request["serialized_body_sha256"],
                "error_type": "RemoteDisconnected",
                "http_status": None,
            }
            with SetWorkflowID(worker_workflow_id):
                handle = DBOS.start_workflow(
                    _worker_workflow,
                    run_id,
                    cursor,
                    worker_responses,
                    review_count,
                    reviewer_responses,
                    continuation_count,
                    unresolved,
                )
        else:
            handle = DBOS.retrieve_workflow(worker_workflow_id)
        result = handle.get_result(polling_interval_sec=1.0)
    finally:
        DBOS.destroy()
    manifest = _build_final_manifest(
        repo_root,
        run_root,
        context,
        result,
        started_at=started_at,
        workflow_was_existing=workflow_was_existing,
    )
    return {
        "status": manifest["status"],
        "run_id": run_id,
        "run_root": run_root.as_posix(),
        "termination_reason": manifest["termination_reason"],
        "worker_model_responses": manifest["worker"]["model_responses"],
        "reviewer_model_responses": manifest["reviewer"]["total_model_responses"],
        "review_count": manifest["reviewer"]["review_count"],
        "artifact_hash_verification": verify_artifact_hashes(run_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", default=RESUME_RUN_ID)
    parser.add_argument("--parent-run-id", default=PARENT_RUN_ID)
    parser.add_argument("--env-file", type=Path, help="Provider environment file; defaults to repository .env or process environment")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--recover-workflow-error", action="store_true")
    action.add_argument("--reconcile-final-artifact-hashes", action="store_true")
    arguments = parser.parse_args()
    if arguments.recover_workflow_error:
        result = recover_failed_resume_segment(arguments.repo_root, run_id=arguments.run_id)
    elif arguments.reconcile_final_artifact_hashes:
        result = reconcile_final_artifact_hashes(arguments.repo_root, run_id=arguments.run_id)
    else:
        result = run_resume_segment(
            arguments.repo_root,
            run_id=arguments.run_id,
            parent_run_id=arguments.parent_run_id,
            env_file=arguments.env_file,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
