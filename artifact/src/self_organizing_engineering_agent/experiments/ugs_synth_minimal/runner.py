"""One-shot conversation runner for the UGS-SYNTH minimal apparatus."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator

from ..pilot_1a.docker_executor import inspect_image
from .runtime import create_minimal_runtime
from .tools import (
    ALLOWED_TOOL_NAMES,
    APPARATUS_ID,
    APPARATUS_CHANGE_REASON,
    APPARATUS_VERSION,
    DEFAULT_MINIMAL_IMAGE,
    native_tool_definitions,
    TOOL_PARAMETER_SCHEMAS,
)


MAX_MODEL_TURNS = 600
MAX_OUTPUT_TOKENS = 65536
MAX_LENGTH_CONTINUATIONS = 3

_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")

SYSTEM_PROMPT = """You are working in a controlled filesystem sandbox. Only read-only brief/ and read-write project/ are visible. Python runs in a resource-limited container with no network connection. No host evaluator or hidden-case data is available during the run.
When you decide that the project is complete, call finish_project.
A normal text response does not by itself mark the project complete."""
INITIAL_AGENT_PROMPT = """Complete the engineering project described in brief/ and provide the deliverables described there. You decide how to carry out the work and when it is complete."""


class NativeToolProvider(Protocol):
    model_id: str

    def generate_with_native_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        max_output_tokens: int | None,
    ) -> Any: ...


class MinimalRunInstrumentation:
    """Append-only trajectory records with no evaluator interface."""

    def __init__(self, run_root: Path) -> None:
        self.host_logs = run_root / "host_logs"
        self.host_logs.mkdir(parents=True, exist_ok=True)
        self.tool_call_count = 0

    @staticmethod
    def _append(path: Path, record: dict[str, Any]) -> None:
        value = {"timestamp": utc_now(), **record}
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")

    def log_message(self, record: dict[str, Any]) -> None:
        self._append(self.host_logs / "messages.jsonl", record)

    def log_tool_call(self, record: dict[str, Any]) -> None:
        self.tool_call_count += 1
        self._append(self.host_logs / "tool_calls.jsonl", record)

    def log_workspace_evolution(self, record: dict[str, Any]) -> None:
        self._append(self.host_logs / "workspace_evolution.jsonl", record)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hash_text(value: str) -> str:
    return _sha256(value.encode("utf-8"))


def _parse_arguments(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw, str):
        return None, "arguments_not_string"
    try:
        value = json.loads(raw, parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
    except (json.JSONDecodeError, ValueError):
        return None, "arguments_invalid_json"
    if not isinstance(value, dict):
        return None, "arguments_not_object"
    return value, None


def _safe_arguments(name: Any, arguments: dict[str, Any] | None) -> dict[str, Any] | None:
    if arguments is None:
        return None
    result = dict(arguments)
    content_key = "content" if name == "write_file" else "code" if name == "execute_python" else None
    if content_key and isinstance(result.get(content_key), str):
        value = result.pop(content_key)
        result[content_key + "_bytes"] = len(value.encode("utf-8"))
        result[content_key + "_sha256"] = _hash_text(value)
    return result


def _tool_message(call_id: str, result: dict[str, Any]) -> dict[str, str]:
    return {"role": "tool", "tool_call_id": call_id, "content": _json(result)}


def _workspace_snapshot(project_root: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted(project_root.rglob("*")):
        relative = path.relative_to(project_root).as_posix()
        if path.is_symlink():
            rows[relative] = {"kind": "symlink", "size_bytes": None, "sha256": None}
        elif path.is_dir():
            rows[relative + "/"] = {"kind": "directory", "size_bytes": None, "sha256": None}
        elif path.is_file():
            raw = path.read_bytes()
            rows[relative] = {"kind": "file", "size_bytes": len(raw), "sha256": _sha256(raw)}
    return rows


def _workspace_manifest(project_root: Path) -> dict[str, Any]:
    files = _workspace_snapshot(project_root)
    return {
        "files": files,
        "file_count": sum(row["kind"] == "file" for row in files.values()),
        "total_file_bytes": sum(row["size_bytes"] or 0 for row in files.values() if row["kind"] == "file"),
    }


def _valid_run_id(run_id: str) -> bool:
    return bool(_RUN_ID_PATTERN.fullmatch(run_id))


def _public_hashes(public_root: Path) -> dict[str, str]:
    return {
        path.relative_to(public_root).as_posix(): _sha256(path.read_bytes())
        for path in sorted(public_root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def _git_head(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5.0,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError("git_head_unavailable") from None
    head = completed.stdout.strip()
    if not head:
        raise RuntimeError("git_head_unavailable")
    return head


def _provider_reproducibility_metadata(
    provider: NativeToolProvider,
    *,
    repo_root: Path,
    definitions: list[dict[str, Any]],
) -> tuple[dict[str, Any], Path]:
    provider_class = type(provider)
    source_name = inspect.getsourcefile(provider_class)
    if not source_name:
        raise RuntimeError("provider_source_unavailable")
    provider_source = Path(source_name).resolve(strict=True)
    try:
        provider_source_relative = provider_source.relative_to(repo_root).as_posix()
    except ValueError:
        raise RuntimeError("provider_source_outside_repository") from None

    configured_model = getattr(provider, "configured_model", None)
    effective_model = getattr(provider, "effective_model", getattr(provider, "model_id", None))
    provider_name = getattr(provider, "provider_name", None)
    build_native_request = getattr(provider, "build_native_tool_request_payload", None)
    if not all(isinstance(value, str) and value for value in (configured_model, effective_model, provider_name)):
        raise RuntimeError("provider_identity_incomplete")
    if configured_model != effective_model:
        raise RuntimeError("configured_and_effective_models_differ")
    if not callable(build_native_request) or not callable(getattr(provider, "generate_with_native_tools", None)):
        raise RuntimeError("native_tool_provider_configuration_unavailable")

    request_profile = build_native_request([], definitions, max_output_tokens=MAX_OUTPUT_TOKENS)
    if request_profile.get("model") != effective_model:
        raise RuntimeError("provider_request_model_mismatch")
    tool_names = [row["function"]["name"] for row in definitions]
    configured_tools = request_profile.get("tools")
    if not isinstance(configured_tools, list) or configured_tools != definitions:
        raise RuntimeError("provider_tool_definition_mismatch")

    provider_source_sha256 = _sha256(provider_source.read_bytes())
    endpoint_host = getattr(provider, "endpoint_host", None)
    if not isinstance(endpoint_host, str) or not endpoint_host:
        base_url = getattr(provider, "base_url", "")
        endpoint_host = urlsplit(base_url).hostname if isinstance(base_url, str) else None
    identity = {
        "provider_name": provider_name,
        "provider_class": f"{provider_class.__module__}.{provider_class.__qualname__}",
        "source_file": provider_source_relative,
        "source_sha256": provider_source_sha256,
    }
    model_configuration = {
        "configured_model": configured_model,
        "effective_model": effective_model,
        "configuration_source": getattr(provider, "model_configuration_source", "not_available"),
        "endpoint_host": endpoint_host or "not_available",
        "thinking": {
            "type": getattr(provider, "thinking", "not_available"),
            "reasoning_effort": getattr(provider, "reasoning_effort", "not_available"),
        },
        "temperature_control": getattr(provider, "temperature_control", "not_available"),
        "timeout_sec": getattr(provider, "timeout_sec", "not_available"),
        "retry_policy": getattr(provider, "retry_policy", "not_available"),
        "fallback_models": list(getattr(provider, "fallback_models", ())),
        "max_model_turns": MAX_MODEL_TURNS,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_consecutive_length_continuations": MAX_LENGTH_CONTINUATIONS,
        "request_token_parameter": "max_tokens" if request_profile.get("max_tokens") == MAX_OUTPUT_TOKENS else "not_available",
    }
    native_tool_configuration = {
        "enabled": True,
        "request_method": "OpenAI-compatible Chat Completions native tools",
        "tool_choice": request_profile.get("tool_choice"),
        "tool_names": tool_names,
        "tool_definitions_sha256": _hash_text(_json(definitions)),
    }
    return (
        {
            "provider_identity": identity,
            "provider_source_sha256": provider_source_sha256,
            "configured_model": configured_model,
            "effective_model": effective_model,
            "model_configuration": model_configuration,
            "native_tool_calling_configuration": native_tool_configuration,
            "credential_source": getattr(provider, "credential_source", {"kind": "not_available"}),
            "credential_configured": bool(getattr(provider, "credential_configured", False)),
            "credential_value_persisted": False,
        },
        provider_source,
    )


def _build_freeze_record(
    provider: NativeToolProvider,
    *,
    repo_root: Path,
    run_id: str,
    image_info: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    if not _valid_run_id(run_id):
        raise ValueError("invalid minimal-runtime run_id")
    definitions = native_tool_definitions()
    public_root = repo_root / "cases" / "ugs_synth_d01" / "public"
    case_metadata = json.loads((public_root / "case.json").read_text(encoding="utf-8"))
    provider_metadata, provider_source = _provider_reproducibility_metadata(
        provider,
        repo_root=repo_root,
        definitions=definitions,
    )
    runtime_paths = [
        Path(__file__),
        Path(__file__).with_name("tools.py"),
        Path(__file__).with_name("isolation.py"),
        Path(__file__).with_name("runtime.py"),
        repo_root / "scripts" / "run_ugs_synth_minimal_development.py",
        repo_root / "docker" / "ugs_synth_minimal" / "Dockerfile",
        repo_root / "src" / "self_organizing_engineering_agent" / "experiments" / "pilot_1a" / "docker_executor.py",
        repo_root / "src" / "self_organizing_engineering_agent" / "experiments" / "pilot_1a" / "isolation.py",
        repo_root / "src" / "self_organizing_engineering_agent" / "experiments" / "pilot_1a" / "instrumentation.py",
        provider_source,
    ]
    runtime_hashes = {path.relative_to(repo_root).as_posix(): _sha256(path.read_bytes()) for path in runtime_paths}
    return {
        "git_head": _git_head(repo_root),
        "case_id": case_metadata["case_id"],
        "case_version": case_metadata["case_version"],
        "apparatus_id": APPARATUS_ID,
        "apparatus_version": APPARATUS_VERSION,
        "apparatus_change_reason": APPARATUS_CHANGE_REASON,
        "run_id": run_id,
        "length_continuation_policy": {
            "max_consecutive_length_continuations": MAX_LENGTH_CONTINUATIONS,
            "replay_full_assistant_message": True,
        },
        "public_world_sha256": _public_hashes(public_root),
        "tool_definitions_sha256": _hash_text(_json(definitions)),
        "prompt_sha256": {"system": _hash_text(SYSTEM_PROMPT), "initial_user": _hash_text(INITIAL_AGENT_PROMPT)},
        "runtime_source_sha256": runtime_hashes,
        "docker_image": image_info,
        **provider_metadata,
        "model_id": provider_metadata["effective_model"],
        "model_turn_limit": MAX_MODEL_TURNS,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "automatic_summarization": False,
        "memory_manager": False,
        "context_reset": False,
        "persistent_workspace": True,
        "hidden_evaluator_connected": False,
        "created_at": created_at,
    }


def _run_conversation(provider: NativeToolProvider, runtime: Any, instrumentation: MinimalRunInstrumentation) -> dict[str, Any]:
    tools = runtime.tools
    definitions = native_tool_definitions()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": INITIAL_AGENT_PROMPT},
    ]
    instrumentation.log_message({"kind": "initial_prompt", "role": "system", "content": SYSTEM_PROMPT})
    instrumentation.log_message({"kind": "initial_prompt", "role": "user", "content": INITIAL_AGENT_PROMPT})

    usage_rows: list[dict[str, Any]] = []
    returned_models: list[str] = []
    calls_per_turn: list[int] = []
    termination = "max_model_turns"
    finish_requested = False
    python_executions = 0
    consecutive_length_continuations = 0
    total_length_continuations = 0
    started = time.perf_counter()

    for turn in range(1, MAX_MODEL_TURNS + 1):
        try:
            generation = provider.generate_with_native_tools(messages, definitions, max_output_tokens=MAX_OUTPUT_TOKENS)
        except Exception as exc:
            details = getattr(exc, "details", {})
            safe_details = {
                key: details[key]
                for key in ("error_type", "category", "http_status", "error_code")
                if isinstance(details, dict) and key in details
            }
            if not safe_details:
                safe_details = {"error_type": type(exc).__name__, "category": "provider_error"}
            instrumentation.log_message({"kind": "provider_error", "turn": turn, "error": safe_details})
            termination = "provider_error"
            break

        usage = getattr(generation, "usage", {})
        usage_rows.append(usage if isinstance(usage, dict) else {})
        returned_model = getattr(generation, "returned_model", None)
        if isinstance(returned_model, str):
            returned_models.append(returned_model)
        assistant = getattr(generation, "assistant_message", None)
        if not isinstance(assistant, dict) or assistant.get("role") != "assistant":
            termination = "invalid_assistant_message"
            instrumentation.log_message({"kind": "protocol_error", "turn": turn, "category": "missing_or_invalid_assistant_message"})
            break
        native_calls = assistant.get("tool_calls") or []
        if not isinstance(native_calls, list):
            termination = "invalid_assistant_message"
            instrumentation.log_message({"kind": "protocol_error", "turn": turn, "category": "tool_calls_not_list"})
            break

        finish_reason = getattr(generation, "finish_reason", None)
        instrumentation.log_message({
            "kind": "model_response",
            "turn": turn,
            "assistant_message": assistant,
            "usage": usage,
            "latency_sec": getattr(generation, "latency_sec", None),
            "finish_reason": finish_reason,
            "http_status": getattr(generation, "http_status", None),
            "returned_model": returned_model,
        })
        messages.append(dict(assistant))
        if not native_calls:
            calls_per_turn.append(0)
            if finish_reason == "length":
                has_continuable_message = any(
                    isinstance(assistant.get(key), str) and bool(assistant[key])
                    for key in ("content", "reasoning_content")
                )
                if has_continuable_message and consecutive_length_continuations < MAX_LENGTH_CONTINUATIONS:
                    consecutive_length_continuations += 1
                    total_length_continuations += 1
                    instrumentation.log_message({
                        "kind": "length_continuation",
                        "turn": turn,
                        "continuation_number": consecutive_length_continuations,
                        "max_consecutive_length_continuations": MAX_LENGTH_CONTINUATIONS,
                        "assistant_message_replayed": True,
                    })
                    continue
                termination = (
                    "output_length_continuation_limit"
                    if has_continuable_message
                    else "truncated_response_without_continuable_content"
                )
                instrumentation.log_message({
                    "kind": "provider_termination",
                    "turn": turn,
                    "finish_reason": finish_reason,
                    "termination_reason": termination,
                })
                break
            if finish_reason == "tool_calls":
                termination = "provider_declared_tool_calls_missing"
                instrumentation.log_message({
                    "kind": "provider_termination",
                    "turn": turn,
                    "finish_reason": finish_reason,
                    "termination_reason": termination,
                })
                break
            if finish_reason in {"content_filter", "insufficient_system_resource", "aborted"}:
                termination = f"provider_{finish_reason}"
                instrumentation.log_message({
                    "kind": "provider_termination",
                    "turn": turn,
                    "finish_reason": finish_reason,
                    "termination_reason": termination,
                })
                break
            consecutive_length_continuations = 0
            termination = "assistant_stopped_without_finish_project"
            break

        consecutive_length_continuations = 0
        calls_per_turn.append(len(native_calls))
        call_ids: set[str] = set()
        for call in native_calls:
            function = call.get("function") if isinstance(call, dict) else None
            name = function.get("name") if isinstance(function, dict) else None
            call_id = call.get("id") if isinstance(call, dict) else None
            raw_arguments = function.get("arguments") if isinstance(function, dict) else None
            arguments, parse_error = _parse_arguments(raw_arguments)
            validation_error = parse_error
            if validation_error is None and (not isinstance(name, str) or name not in ALLOWED_TOOL_NAMES):
                validation_error = "unknown_native_tool"
            if validation_error is None and arguments is not None:
                errors = list(Draft202012Validator(TOOL_PARAMETER_SCHEMAS[name]).iter_errors(arguments))
                if errors:
                    validation_error = "tool_schema_violation"
            if not isinstance(call_id, str) or not call_id or call_id in call_ids:
                result = {"error_category": "invalid_native_tool_call", "tool_error": "missing or duplicate tool call id"}
                if not isinstance(call_id, str) or not call_id:
                    termination = "native_tool_call_missing_id"
                else:
                    termination = "native_tool_call_duplicate_id"
                instrumentation.log_tool_call({"turn": turn, "tool_call_id": call_id, "tool": name, "validation_status": termination, "result": result})
                continue
            call_ids.add(call_id)

            if validation_error is not None or arguments is None:
                category = validation_error or "invalid_native_tool_arguments"
                result = {"error_category": category, "tool_error": "invalid native tool arguments"}
            else:
                category = None
                mutating = name in {"write_file", "execute_python"}
                before = _workspace_snapshot(tools.sandbox.project_root) if mutating else {}
                try:
                    result = tools.dispatch(name, arguments)
                except Exception as exc:
                    category = "tool_runtime_error"
                    result = {"error_category": category, "tool_error": type(exc).__name__}
                if mutating:
                    after = _workspace_snapshot(tools.sandbox.project_root)
                    for path in sorted(before.keys() | after.keys()):
                        old, new = before.get(path), after.get(path)
                        if old != new:
                            row = new or old or {}
                            instrumentation.log_workspace_evolution({
                                "turn": turn,
                                "tool_call_id": call_id,
                                "path": "project/" + path,
                                "action": "create" if old is None else "delete" if new is None else "modify",
                                "size_bytes": row.get("size_bytes"),
                                "sha256": row.get("sha256"),
                            })
                    if name == "execute_python":
                        python_executions += 1
                if isinstance(result, dict) and result.get("status") == "finish_requested":
                    finish_requested = True

            instrumentation.log_tool_call({
                "turn": turn,
                "tool_call_id": call_id,
                "tool": name,
                "arguments": _safe_arguments(name, arguments),
                "validation_status": category or "valid",
                "result": result,
            })
            instrumentation.log_message({"kind": "tool_result", "turn": turn, "tool_call_id": call_id, "content": result})
            messages.append(_tool_message(call_id, result))

        if termination.startswith("native_tool_call_"):
            break
        if finish_requested:
            termination = "agent_completed"
            break

    return {
        "termination_reason": termination,
        "actual_model_turns": len(usage_rows),
        "calls_per_turn": calls_per_turn,
        "usage_rows": usage_rows,
        "returned_models": returned_models,
        "runtime_duration_sec": round(time.perf_counter() - started, 6),
        "finish_requested": finish_requested,
        "python_executions": python_executions,
        "native_tool_calls": instrumentation.tool_call_count,
        "length_continuations": total_length_continuations,
    }


def _aggregate_usage(rows: list[dict[str, Any]]) -> dict[str, int | str]:
    keys = ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "cached_input_tokens", "prompt_cache_miss_tokens")
    result: dict[str, int | str] = {}
    for key in keys:
        values = [row.get(key) for row in rows]
        result[key] = sum(value for value in values if isinstance(value, int) and not isinstance(value, bool)) if values and all(isinstance(value, int) and not isinstance(value, bool) for value in values) else "not_available"
    return result


def run_minimal_development(
    provider: NativeToolProvider,
    *,
    repo_root: Path,
    runs_root: Path,
    run_id: str,
    image: str = DEFAULT_MINIMAL_IMAGE,
) -> dict[str, Any]:
    """Run one minimal-runtime trajectory; this function is never called by runtime tests."""

    repo_root = repo_root.resolve()
    runs_root = runs_root.resolve()
    if not _valid_run_id(run_id):
        raise ValueError("invalid minimal-runtime run_id")
    run_root = runs_root / run_id
    freeze_path = run_root / "freeze.json"
    if run_root.exists():
        raise FileExistsError("minimal-runtime run identity already exists; do not resume or overwrite")

    image_info = inspect_image(image)
    if not image_info.get("available"):
        raise RuntimeError("minimal_python_image_unavailable")
    freeze = _build_freeze_record(
        provider,
        repo_root=repo_root,
        run_id=run_id,
        image_info=image_info,
        created_at=utc_now(),
    )
    run_root.mkdir(parents=True, exist_ok=False)
    with freeze_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(freeze, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    freeze_sha256 = _sha256(freeze_path.read_bytes())

    runtime = create_minimal_runtime(repo_root, run_root / "sandbox", image=image)
    instrumentation = MinimalRunInstrumentation(run_root)
    started_at = utc_now()
    loop = _run_conversation(provider, runtime, instrumentation)
    workspace = _workspace_manifest(runtime.sandbox.project_root)
    manifest = {
        "apparatus_id": APPARATUS_ID,
        "apparatus_version": APPARATUS_VERSION,
        "run_id": run_id,
        "status": "agent_completed_without_evaluation" if loop["termination_reason"] == "agent_completed" else "terminated_without_finish",
        "termination_reason": loop["termination_reason"],
        "model_id": getattr(provider, "model_id", None),
        "start_time": started_at,
        "end_time": utc_now(),
        "runtime_duration_sec": loop["runtime_duration_sec"],
        "actual_model_turns": loop["actual_model_turns"],
        "native_tool_calls": loop["native_tool_calls"],
        "tool_calls_per_turn": loop["calls_per_turn"],
        "python_executions": loop["python_executions"],
        "returned_models": loop["returned_models"],
        "token_usage": _aggregate_usage(loop["usage_rows"]),
        "token_usage_rows": loop["usage_rows"],
        "length_continuations": loop["length_continuations"],
        "finish_requested": loop["finish_requested"],
        "workspace": workspace,
        "hidden_evaluator_connected": False,
        "automatic_summarization": False,
        "memory_manager": False,
        "context_reset": False,
        "persistent_workspace": True,
        "freeze_file": "freeze.json",
        "minimal_runtime_freeze_sha256": freeze_sha256,
    }
    (run_root / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    artifact_paths = [path for path in run_root.rglob("*") if path.is_file() and path.name != "artifact_hashes.json"]
    artifact_hashes = {path.relative_to(run_root).as_posix(): _sha256(path.read_bytes()) for path in sorted(artifact_paths)}
    (run_root / "artifact_hashes.json").write_text(json.dumps(artifact_hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {
        "status": manifest["status"],
        "run_id": run_id,
        "run_root": run_root.as_posix(),
        "termination_reason": loop["termination_reason"],
        "actual_model_turns": loop["actual_model_turns"],
        "native_tool_calls": loop["native_tool_calls"],
        "python_executions": loop["python_executions"],
    }
