"""Start or resume a fresh Worker-only or explicit-collaboration DBOS run."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from dbos import DBOS, SetWorkflowID

from ..pilot_1a.deepseek_provider import DeepSeekProvider
from ..pilot_1a.docker_executor import DockerExecutor, inspect_image
from ..pilot_1a.isolation import AgentSandbox
from ..ugs_synth_minimal.runner import INITIAL_AGENT_PROMPT, SYSTEM_PROMPT, _git_head, _workspace_manifest
from ..ugs_synth_minimal.tools import DEFAULT_MINIMAL_IMAGE, MinimalUGSSynthTools, native_tool_definitions
from . import APPARATUS_ID, APPARATUS_VERSION as BASE_APPARATUS_VERSION
from .durable_resume import _provider_env_file, _sqlite_url, _write_json
from .durable_runtime import (
    DURABLE_APPARATUS_VERSION,
    DurableProviderBoundaryLogger,
    DurableRuntimeContext,
    _worker_workflow,
    configure_runtime,
)
from .durable_store import DurableStore, sha256_json, utc_now
from .provider_boundary import LOGGING_SCHEMA_VERSION, RAW_RESPONSE_CAPTURE_LEVEL, REDACTION_POLICY_VERSION
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
    WORKER_REVIEWER_CAPABILITY_STATEMENT,
    WORKER_SYSTEM_PROMPT,
    _hash_text,
    _probe_reviewer_runtime,
    _probe_worker_runtime,
    _provider_record,
    _tree_manifest,
    _usage_totals,
)
from .tools import reviewer_tool_definitions, worker_tool_definitions


Condition = Literal["worker_only", "explicit_collaboration"]
RUNS_PARENT = Path("runs/ugs_synth_interleaved_review")
PRICING_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing/"
PRICING_CAPTURE_DATE = "2026-09-24"
DEEPSEEK_FLASH_RATES_PER_MILLION = {
    "off_peak": {"cache_hit_input": 0.022, "cache_miss_input": 0.66, "output": 1.98},
    "peak": {"cache_hit_input": 0.044, "cache_miss_input": 1.32, "output": 3.96},
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _public_world(repo_root: Path) -> tuple[Path, dict[str, str]]:
    public_root = repo_root / "cases" / "ugs_synth_d01" / "public"
    if not public_root.is_dir():
        raise FileNotFoundError("public_world_missing")
    rows = {
        path.relative_to(public_root).as_posix(): _sha256(path.read_bytes())
        for path in sorted(public_root.rglob("*"))
        if path.is_file()
    }
    if not rows:
        raise RuntimeError("public_world_empty")
    return public_root, rows


def _sandbox(root: Path, *, reviewer: bool, public_root: Path) -> AgentSandbox:
    actor_root = root / ("reviewer" if reviewer else "worker") / "sandbox"
    view_root = actor_root / "agent_view"
    brief_root = view_root / "brief"
    project_root = view_root / ("review" if reviewer else "project")
    view_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(public_root, brief_root)
    project_root.mkdir(parents=True, exist_ok=True)
    for path in sorted(brief_root.rglob("*"), reverse=True):
        if not path.is_symlink():
            path.chmod(0o555 if path.is_dir() else 0o444)
    brief_root.chmod(0o555)
    sandbox = AgentSandbox(
        run_root=actor_root.resolve(),
        agent_view=view_root.resolve(),
        brief_root=brief_root.resolve(),
        project_root=project_root.resolve(),
    )
    if reviewer:
        (root / "reviewer" / "submission_snapshots").mkdir(parents=True, exist_ok=True)
    return sandbox


def _environment_record(repo_root: Path, env_file: Path | None) -> dict[str, Any]:
    repository_dotenv = repo_root / ".env"
    selected = env_file.resolve(strict=True) if env_file is not None else repository_dotenv
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", ".env"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    ).returncode == 0
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", ".env"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    ).returncode == 0
    return {
        "provider_environment_file_present": selected.is_file(),
        "repository_dotenv_ignored_by_git": ignored,
        "repository_dotenv_tracked_by_git": tracked,
        "environment_file_copied_to_run": False,
        "credential_value_persisted": False,
        "credential_name": "DEEPSEEK_API_KEY",
        "selection": "explicit_path" if env_file is not None else "repository_local_dotenv_or_process_environment",
    }


def _tool_names(definitions: list[dict[str, Any]]) -> list[str]:
    return [row["function"]["name"] for row in definitions]


def _source_hashes(repo_root: Path) -> dict[str, str]:
    paths = (
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/durable_runtime.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/durable_store.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/durable_resume.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/durable_replication.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/provider_boundary.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/runner.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_interleaved_review/tools.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_minimal/runner.py",
        "src/self_organizing_engineering_agent/experiments/ugs_synth_minimal/tools.py",
        "src/self_organizing_engineering_agent/experiments/pilot_1a/deepseek_provider.py",
        "docker/ugs_synth_minimal/Dockerfile",
        "pyproject.toml",
        "uv.lock",
    )
    return {
        relative: _sha256((repo_root / relative).read_bytes())
        for relative in paths
        if (repo_root / relative).is_file()
    }


def _seed_message(store: DurableStore, actor: str, index: int, message: dict[str, Any], kind: str) -> None:
    message_id = f"initial:{actor}:{index:02d}"
    store.append_conversation_message(actor, message_id, message)
    store.append_evidence(f"{actor}/host_logs/messages.jsonl", message_id, {"kind": kind, **message})


def _prepare_fresh_run(
    repo_root: Path,
    *,
    runs_root: Path,
    run_id: str,
    condition: Condition,
    env_file: Path | None,
    image: str,
) -> tuple[Path, DurableRuntimeContext, DeepSeekProvider, DeepSeekProvider | None]:
    repo_root = repo_root.resolve(strict=True)
    public_root, public_hashes = _public_world(repo_root)
    provider_env = _provider_env_file(repo_root, env_file)
    worker_provider = DeepSeekProvider(env_file=provider_env)
    reviewer_enabled = condition == "explicit_collaboration"
    reviewer_provider = DeepSeekProvider(env_file=provider_env) if reviewer_enabled else None
    if reviewer_provider is worker_provider:
        raise RuntimeError("provider_instances_must_be_independent")

    run_root = runs_root.resolve() / run_id
    if run_root.exists():
        raise FileExistsError("run_identity_already_exists; preserve existing run evidence")
    image_info = inspect_image(image)
    if not image_info.get("available"):
        raise RuntimeError("durable_replication_docker_image_unavailable")

    run_root.mkdir(parents=True, exist_ok=False)
    worker_sandbox = _sandbox(run_root, reviewer=False, public_root=public_root)
    reviewer_sandbox = (
        _sandbox(run_root, reviewer=True, public_root=public_root)
        if reviewer_enabled
        else None
    )
    worker_executor = DockerExecutor(
        image=image,
        brief_root=worker_sandbox.brief_root,
        project_root=worker_sandbox.project_root,
    )
    worker_probe = _probe_worker_runtime(SimpleNamespace(executor=worker_executor))
    reviewer_probe = _probe_reviewer_runtime(reviewer_sandbox, image) if reviewer_enabled and reviewer_sandbox else None
    if worker_probe.get("passed") is not True:
        raise RuntimeError("durable_replication_worker_container_probe_failed")
    if reviewer_enabled and reviewer_probe and reviewer_probe.get("passed") is not True:
        raise RuntimeError("durable_replication_reviewer_container_probe_failed")

    worker_definitions = worker_tool_definitions() if reviewer_enabled else native_tool_definitions()
    reviewer_definitions = reviewer_tool_definitions() if reviewer_enabled else []
    worker_system_prompt = WORKER_SYSTEM_PROMPT if reviewer_enabled else SYSTEM_PROMPT
    environment = _environment_record(repo_root, env_file)
    worker_record = _provider_record(worker_provider, repo_root=repo_root, definitions=worker_definitions)
    reviewer_record = (
        _provider_record(reviewer_provider, repo_root=repo_root, definitions=reviewer_definitions)
        if reviewer_provider is not None
        else None
    )
    if provider_env is not None and not environment["provider_environment_file_present"]:
        raise RuntimeError("provider_environment_file_missing")

    project_manifest = _workspace_manifest(worker_sandbox.project_root)
    review_manifest = _workspace_manifest(reviewer_sandbox.project_root) if reviewer_sandbox else None
    if project_manifest.get("file_count") != 0 or (review_manifest is not None and review_manifest.get("file_count") != 0):
        raise RuntimeError("fresh_replication_workspace_not_empty")

    runtime_root = run_root / "runtime"
    store = DurableStore(runtime_root, run_id=run_id)
    boundary_logger = DurableProviderBoundaryLogger(run_root, run_id, store)
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
        boundary_logger=boundary_logger,
        image_info=image_info,
        lineage={
            "trajectory_relationship": "independent_replication",
            "paired_group_id": "ugs_synth_paired_replication_001",
            "condition": condition,
        },
        reviewer_enabled=reviewer_enabled,
    )
    configure_runtime(context)
    initial_worker_messages = (
        {"role": "system", "content": worker_system_prompt},
        {"role": "user", "content": INITIAL_AGENT_PROMPT},
    )
    for index, message in enumerate(initial_worker_messages, start=1):
        _seed_message(store, "worker", index, message, "initial_prompt")
    if reviewer_enabled:
        initial_reviewer_messages = (
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": REVIEWER_INITIAL_PROMPT},
        )
        for index, message in enumerate(initial_reviewer_messages, start=1):
            _seed_message(store, "reviewer", index, message, "initial_prompt")

    checks = {
        "public_world_copied_from_frozen_source": True,
        "public_world_sha256": sha256_json(public_hashes),
        "worker_project_empty_before_first_request": True,
        "reviewer_context_enabled": reviewer_enabled,
        "review_workspace_empty_before_first_request": not reviewer_enabled or (review_manifest is not None and review_manifest.get("file_count") == 0),
        "worker_tool_names": _tool_names(worker_definitions),
        "worker_only_baseline_tool_surface": (
            _tool_names(worker_definitions) == _tool_names(native_tool_definitions())
            if not reviewer_enabled
            else None
        ),
        "explicit_review_tool_added_only": (
            _tool_names(worker_definitions) == [*_tool_names(native_tool_definitions()), "submit_for_review"]
            if reviewer_enabled
            else None
        ),
        "worker_container_isolation_probe": worker_probe,
        "reviewer_container_isolation_probe": reviewer_probe,
        "provider_environment": environment,
        "worker_provider_profile_valid": worker_record["configured_model"] == worker_record["effective_model"] == "deepseek-flash",
        "reviewer_provider_profile_valid": reviewer_record is None or reviewer_record["configured_model"] == reviewer_record["effective_model"] == "deepseek-flash",
        "provider_instances_independent": reviewer_provider is None or reviewer_provider is not worker_provider,
        "formal_evaluator_connected": False,
        "formal_state": "UGS_FORMAL_STATE=NOT READY",
    }
    if reviewer_enabled and _tool_names(worker_definitions) != [*_tool_names(native_tool_definitions()), "submit_for_review"]:
        raise RuntimeError("explicit_collaboration_tool_surface_changed")
    if not reviewer_enabled and _tool_names(worker_definitions) != _tool_names(native_tool_definitions()):
        raise RuntimeError("worker_only_tool_surface_changed")

    freeze = {
        "apparatus_id": APPARATUS_ID,
        "apparatus_version": DURABLE_APPARATUS_VERSION,
        "base_apparatus_version": BASE_APPARATUS_VERSION,
        "run_id": run_id,
        "condition": condition,
        "trajectory_relationship": "independent_replication",
        "paired_group_id": "ugs_synth_paired_replication_001",
        "paired_with": (
            "ugs_synth_explicit_collaboration_replication_001"
            if condition == "worker_only"
            else "ugs_synth_worker_only_replication_001"
        ),
        "created_at": utc_now(),
        "git_head": _git_head(repo_root),
        "dbos": {
            "runtime": "DBOS",
            "version": importlib.metadata.version("dbos"),
            "workflow_id": f"{run_id}:worker",
            "reviewer_workflow_id_pattern": f"{run_id}:reviewer:NNNN" if reviewer_enabled else None,
            "system_database_path": "runtime/dbos.sqlite",
            "recovery_ledger_path": "runtime/recovery_ledger.sqlite",
        },
        "public_world_sha256": sha256_json(public_hashes),
        "public_world_files": public_hashes,
        "worker_system_prompt_sha256": _hash_text(worker_system_prompt),
        "worker_initial_user_prompt_sha256": _hash_text(INITIAL_AGENT_PROMPT),
        "worker_reviewer_capability_statement": WORKER_REVIEWER_CAPABILITY_STATEMENT if reviewer_enabled else None,
        "reviewer_system_prompt_sha256": _hash_text(REVIEWER_SYSTEM_PROMPT) if reviewer_enabled else None,
        "reviewer_initial_user_prompt_sha256": _hash_text(REVIEWER_INITIAL_PROMPT) if reviewer_enabled else None,
        "worker_tool_definitions_sha256": _hash_text(json.dumps(worker_definitions, ensure_ascii=False, sort_keys=True)),
        "reviewer_tool_definitions_sha256": _hash_text(json.dumps(reviewer_definitions, ensure_ascii=False, sort_keys=True)) if reviewer_enabled else None,
        "worker_provider": worker_record,
        "reviewer_provider": reviewer_record,
        "provider_instances_independent": reviewer_provider is None or reviewer_provider is not worker_provider,
        "docker_image": image_info,
        "runtime_source_sha256": _source_hashes(repo_root),
        "durable_retry_policy": {
            "short_attempts": MAX_PROVIDER_TOTAL_ATTEMPTS,
            "short_retry_delays_sec": list(PROVIDER_TRANSPORT_RETRY_DELAYS_SEC),
            "long_backoff_seconds": [60, 120, 300, 600, 600],
            "long_backoff_repeats_last_interval_until_provider_recovers": True,
            "possible_duplicate_provider_execution": True,
        },
        "model_response_safety_limits": {
            "worker_max_responses": WORKER_MAX_MODEL_RESPONSES,
            "reviewer_max_responses_per_review": REVIEWER_MAX_RESPONSES_PER_REVIEW if reviewer_enabled else 0,
            "reviewer_max_total_responses": REVIEWER_MAX_TOTAL_RESPONSES if reviewer_enabled else 0,
            "max_output_tokens_per_response": MAX_OUTPUT_TOKENS,
        },
        "tool_execution_semantics": {
            "local_tool_ledger_durable": True,
            "workspace_state_durable": True,
            "reviewer_history_durable": reviewer_enabled,
            "provider_exactly_once_guaranteed": False,
            "possible_duplicate_provider_execution_recorded": True,
            "uncertain_execute_python_side_effect_stops_for_reconciliation": True,
        },
        "capabilities": {
            "worker_tools": _tool_names(worker_definitions),
            "reviewer_available": reviewer_enabled,
            "planner": False,
            "predefined_workflow": False,
            "optimizer": False,
            "engineering_helper": False,
            "engineering_evaluator": False,
            "python": "generic offline Python in resource-limited Docker container",
        },
        "environment": environment,
        "provider_credential_present": bool(worker_provider.credential_configured),
        "pricing_snapshot": {
            "source": PRICING_SOURCE,
            "captured_date": PRICING_CAPTURE_DATE,
            "model_alias": "deepseek-flash",
            "currency": "USD",
            "rates_per_million_tokens": DEEPSEEK_FLASH_RATES_PER_MILLION,
            "peak_window_utc": "Monday-Friday 01:00-04:00 and 06:00-10:00 UTC",
            "estimate_method": "per-response API usage timestamp; provider invoice unavailable",
        },
        "pre_run_checks": checks,
        "hidden_evaluator_connected": False,
        "formal_state": "UGS_FORMAL_STATE=NOT READY",
        "provider_boundary_logging": "enabled",
        "logging_schema_version": LOGGING_SCHEMA_VERSION,
        "redaction_policy_version": REDACTION_POLICY_VERSION,
        "raw_response_capture_level": RAW_RESPONSE_CAPTURE_LEVEL,
        "automatic_summarization": False,
        "memory_manager": False,
        "context_reset": False,
    }
    _write_json(run_root / "freeze.json", freeze, exclusive=True)
    freeze_sha256 = _sha256((run_root / "freeze.json").read_bytes())
    _write_json(run_root / "pre_run_checks.json", {"checked_at": utc_now(), "checks": checks}, exclusive=True)
    _write_json(
        run_root / "run_manifest.json",
        {
            "run_id": run_id,
            "condition": condition,
            "trajectory_relationship": "independent_replication",
            "paired_group_id": "ugs_synth_paired_replication_001",
            "start_time": utc_now(),
            "end_time": None,
            "status": "running",
            "termination_reason": None,
            "freeze_file": "freeze.json",
            "freeze_sha256": freeze_sha256,
            "dbos": freeze["dbos"],
            "pre_run_checks": checks,
            "formal_state": "UGS_FORMAL_STATE=NOT READY",
        },
        exclusive=True,
    )
    return run_root, context, worker_provider, reviewer_provider


def _load_existing_run(
    repo_root: Path,
    *,
    run_root: Path,
    run_id: str,
    condition: Condition,
    env_file: Path | None,
    image: str,
) -> tuple[DurableRuntimeContext, DeepSeekProvider, DeepSeekProvider | None, dict[str, Any]]:
    manifest_path = run_root / "run_manifest.json"
    freeze_path = run_root / "freeze.json"
    if not manifest_path.is_file() or not freeze_path.is_file():
        raise RuntimeError("partial_run_setup_preserved_but_not_resumable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "running" or freeze.get("run_id") != run_id or freeze.get("condition") != condition:
        raise RuntimeError("existing_run_identity_or_condition_mismatch")
    public_root, public_hashes = _public_world(repo_root)
    if freeze.get("public_world_sha256") != sha256_json(public_hashes):
        raise RuntimeError("frozen_public_world_changed_since_run_start")
    image_info = inspect_image(image)
    frozen_image = freeze.get("docker_image", {})
    if not image_info.get("available") or image_info.get("image_id") != frozen_image.get("image_id"):
        raise RuntimeError("durable_resume_docker_image_identity_changed")

    worker_root = run_root / "worker" / "sandbox"
    worker_sandbox = AgentSandbox(
        run_root=worker_root.resolve(),
        agent_view=(worker_root / "agent_view").resolve(),
        brief_root=(worker_root / "agent_view" / "brief").resolve(),
        project_root=(worker_root / "agent_view" / "project").resolve(),
    )
    reviewer_enabled = condition == "explicit_collaboration"
    reviewer_root = run_root / "reviewer" / "sandbox"
    reviewer_sandbox = (
        AgentSandbox(
            run_root=reviewer_root.resolve(),
            agent_view=(reviewer_root / "agent_view").resolve(),
            brief_root=(reviewer_root / "agent_view" / "brief").resolve(),
            project_root=(reviewer_root / "agent_view" / "review").resolve(),
        )
        if reviewer_enabled
        else None
    )
    provider_env = _provider_env_file(repo_root, env_file)
    worker_provider = DeepSeekProvider(env_file=provider_env)
    reviewer_provider = DeepSeekProvider(env_file=provider_env) if reviewer_enabled else None
    worker_definitions = worker_tool_definitions() if reviewer_enabled else native_tool_definitions()
    reviewer_definitions = reviewer_tool_definitions() if reviewer_enabled else []
    worker_record = _provider_record(worker_provider, repo_root=repo_root, definitions=worker_definitions)
    reviewer_record = (
        _provider_record(reviewer_provider, repo_root=repo_root, definitions=reviewer_definitions)
        if reviewer_provider is not None
        else None
    )
    provider_fields = ("provider_name", "configured_model", "effective_model", "endpoint_host", "thinking", "reasoning_effort", "native_tool_calling")
    for current, frozen in ((worker_record, freeze.get("worker_provider", {})), (reviewer_record, freeze.get("reviewer_provider", {}))):
        if current is None and frozen is None:
            continue
        if current is None or frozen is None or any(current.get(key) != frozen.get(key) for key in provider_fields):
            raise RuntimeError("durable_resume_provider_configuration_changed")
    worker_prompt = WORKER_SYSTEM_PROMPT if reviewer_enabled else SYSTEM_PROMPT
    if freeze.get("worker_system_prompt_sha256") != _hash_text(worker_prompt):
        raise RuntimeError("durable_resume_worker_prompt_changed")
    if freeze.get("worker_tool_definitions_sha256") != _hash_text(json.dumps(worker_definitions, ensure_ascii=False, sort_keys=True)):
        raise RuntimeError("durable_resume_worker_tool_surface_changed")
    if reviewer_enabled:
        if freeze.get("reviewer_tool_definitions_sha256") != _hash_text(json.dumps(reviewer_definitions, ensure_ascii=False, sort_keys=True)):
            raise RuntimeError("durable_resume_reviewer_tool_surface_changed")
    worker_executor = DockerExecutor(image=image, brief_root=worker_sandbox.brief_root, project_root=worker_sandbox.project_root)
    store = DurableStore(run_root / "runtime", run_id=run_id)
    boundary_logger = DurableProviderBoundaryLogger(run_root, run_id, store)
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
        boundary_logger=boundary_logger,
        image_info=image_info,
        lineage={
            "trajectory_relationship": "independent_replication",
            "paired_group_id": "ugs_synth_paired_replication_001",
            "condition": condition,
        },
        reviewer_enabled=reviewer_enabled,
    )
    configure_runtime(context)
    return context, worker_provider, reviewer_provider, manifest


def _peak_utc(timestamp: str | None) -> bool:
    if not isinstance(timestamp, str):
        return False
    try:
        value = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return False
    return value.weekday() < 5 and (1 <= value.hour < 4 or 6 <= value.hour < 10)


def _usage_and_cost(responses: list[dict[str, Any]]) -> tuple[dict[str, int | str], dict[str, Any]]:
    usage_rows = [row.get("usage", {}) for row in responses if isinstance(row.get("usage"), dict)]
    totals = _usage_totals(usage_rows)
    estimate = 0.0
    priced = 0
    peak_rows = 0
    for row in responses:
        usage = row.get("usage")
        if not isinstance(usage, dict):
            continue
        prompt = usage.get("prompt_tokens")
        output = usage.get("completion_tokens")
        hit = usage.get("prompt_cache_hit_tokens", usage.get("cached_tokens"))
        miss = usage.get("prompt_cache_miss_tokens")
        if not all(isinstance(item, int) and not isinstance(item, bool) for item in (prompt, output)):
            continue
        if not isinstance(hit, int) or isinstance(hit, bool):
            hit = 0
        if not isinstance(miss, int) or isinstance(miss, bool):
            miss = max(0, prompt - hit)
        rate_name = "peak" if _peak_utc(row.get("timestamp")) else "off_peak"
        rates = DEEPSEEK_FLASH_RATES_PER_MILLION[rate_name]
        estimate += (hit * rates["cache_hit_input"] + miss * rates["cache_miss_input"] + output * rates["output"]) / 1_000_000
        priced += 1
        peak_rows += rate_name == "peak"
    return totals, {
        "available": priced > 0,
        "estimated_cost_usd": round(estimate, 6) if priced else None,
        "priced_response_count": priced,
        "peak_priced_response_count": peak_rows,
        "source": PRICING_SOURCE,
        "captured_date": PRICING_CAPTURE_DATE,
        "estimate_only_not_provider_invoice": True,
        "possible_duplicate_provider_execution_cost_not_included": True,
    }


def _artifact_hashes(run_root: Path) -> dict[str, str]:
    return {
        path.relative_to(run_root).as_posix(): _sha256(path.read_bytes())
        for path in sorted(run_root.rglob("*"))
        if path.is_file() and path.name != "artifact_hashes.json"
    }


def verify_run_artifacts(run_root: Path) -> dict[str, Any]:
    hash_path = run_root / "artifact_hashes.json"
    if not hash_path.is_file():
        return {"status": "missing_manifest", "files_checked": 0, "mismatches": []}
    expected = json.loads(hash_path.read_text(encoding="utf-8"))
    mismatches = []
    for relative, digest in expected.items():
        path = run_root / Path(relative)
        if not path.is_file():
            mismatches.append({"path": relative, "kind": "missing"})
        elif _sha256(path.read_bytes()) != digest:
            mismatches.append({"path": relative, "kind": "hash_mismatch"})
    return {"status": "passed" if not mismatches else "mismatch", "files_checked": len(expected), "mismatches": mismatches}


def _final_manifest(
    context: DurableRuntimeContext,
    worker_result: dict[str, Any],
    original_manifest: dict[str, Any],
) -> dict[str, Any]:
    store = context.store
    worker_rows = store.evidence("worker/host_logs/messages.jsonl")
    reviewer_rows = store.evidence("reviewer/host_logs/messages.jsonl")
    worker_responses = [row for row in worker_rows if row.get("kind") == "model_response"]
    reviewer_responses = [row for row in reviewer_rows if row.get("kind") == "model_response"]
    worker_usage, worker_cost = _usage_and_cost(worker_responses)
    reviewer_usage, reviewer_cost = _usage_and_cost(reviewer_responses)
    review_rows = sorted(store.evidence("reviewer/reviews.jsonl"), key=lambda row: int(row.get("review_number", 0)))
    worker_tools = [row for row in store.tool_rows() if row.get("actor") == "worker"]
    reviewer_tools = [row for row in store.tool_rows() if row.get("actor") == "reviewer"]
    events = store.event_rows()
    starts = store.process_start_count()
    termination = worker_result.get("termination_reason")
    finished_at = utc_now()
    duration = None
    try:
        start_time = datetime.fromisoformat(str(original_manifest["start_time"]).replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
        duration = round((end_time - start_time).total_seconds(), 3)
    except (KeyError, ValueError):
        pass
    return {
        **original_manifest,
        "end_time": finished_at,
        "runtime_duration_sec": duration,
        "status": "agent_completed_without_evaluation" if termination == "agent_completed" else "terminated_without_finish_project",
        "termination_reason": termination,
        "runtime_process_start_count": starts,
        "runtime_process_restarts": max(0, starts - 1),
        "worker": {
            "termination_reason": termination,
            "model_responses": len(worker_responses),
            "provider_request_attempts": store.provider_attempt_count("worker"),
            "tool_calls": len(worker_tools),
            "tool_calls_by_name": {name: sum(row.get("tool_name") == name for row in worker_tools) for name in sorted({row.get("tool_name", "unknown") for row in worker_tools})},
            "write_calls": sum(row.get("tool_name") == "write_file" for row in worker_tools),
            "python_executions": sum(row.get("tool_name") == "execute_python" for row in worker_tools),
            "review_requests": review_rows,
            "finish_requested": worker_result.get("finish_requested", False),
            "token_usage": worker_usage,
            "cost_estimate": worker_cost,
            "workspace": _workspace_manifest(context.worker_sandbox.project_root),
        },
        "reviewer": {
            "enabled": context.reviewer_enabled,
            "model_responses": len(reviewer_responses),
            "provider_request_attempts": store.provider_attempt_count("reviewer"),
            "tool_calls": len(reviewer_tools),
            "review_count": len(review_rows),
            "first_review_worker_response": review_rows[0].get("global_worker_response") if review_rows else None,
            "findings_count": sum(len(row.get("findings", [])) for row in review_rows if isinstance(row.get("findings", []), list)),
            "reviews": review_rows,
            "token_usage": reviewer_usage,
            "cost_estimate": reviewer_cost,
            "workspace": _workspace_manifest(context.reviewer_sandbox.project_root) if context.reviewer_enabled else None,
            "independent_model_context": context.reviewer_enabled,
            "context_reset_between_reviews": False,
        },
        "provider_attempts": {
            "worker": store.provider_attempt_rows("worker"),
            "reviewer": store.provider_attempt_rows("reviewer") if context.reviewer_enabled else [],
        },
        "runtime_events": {
            "provider_suspensions": sum(row.get("event") == "EXTERNAL_DEPENDENCY_SUSPENDED" for row in events),
            "provider_resumes": sum(row.get("event") == "TRAJECTORY_RESUMED" for row in events),
            "review_completed": sum(row.get("event") == "REVIEW_COMPLETED" for row in events),
            "possible_duplicate_provider_execution": any(row.get("possible_duplicate_provider_execution") for row in store.provider_attempt_rows("worker") + store.provider_attempt_rows("reviewer")),
            "workflow_fork_recovery_count": sum(
                1 for line in (context.run_root / "runtime" / "workflow_recovery.jsonl").read_text(encoding="utf-8").splitlines()
                if json.loads(line).get("event") == "WORKER_WORKFLOW_RECOVERED"
            ) if (context.run_root / "runtime" / "workflow_recovery.jsonl").is_file() else 0,
        },
        "hidden_evaluator_connected": False,
        "formal_state": "UGS_FORMAL_STATE=NOT READY",
    }


def _run_dbos(
    context: DurableRuntimeContext,
) -> dict[str, Any]:
    store = context.store
    run_id = context.run_id
    worker_id = f"{run_id}:worker"
    cursor = store.conversation_count("worker")
    worker_responses = store.evidence_count("worker/host_logs/messages.jsonl", kind="model_response")
    reviewer_responses = store.evidence_count("reviewer/host_logs/messages.jsonl", kind="model_response")
    review_count = len(store.evidence("reviewer/reviews.jsonl"))
    continuations = store.evidence_count("worker/host_logs/messages.jsonl", kind="length_continuation")
    store.record_process_start(f"{os.getpid()}:{uuid.uuid4()}")
    dbos_path = context.run_root / "runtime" / "dbos.sqlite"
    DBOS.destroy()
    DBOS(config={
        "name": "ugs_synth_interleaved_review_durable",
        "application_version": DURABLE_APPARATUS_VERSION,
        "system_database_url": _sqlite_url(dbos_path),
    })
    DBOS.launch()
    try:
        status = DBOS.get_workflow_status(worker_id)
        if status is None:
            with SetWorkflowID(worker_id):
                handle = DBOS.start_workflow(
                    _worker_workflow,
                    run_id,
                    cursor,
                    worker_responses,
                    review_count,
                    reviewer_responses,
                    continuations,
                    None,
                )
        else:
            if status.status == "ERROR":
                return _recover_failed_workflow_tree(context, worker_id)
            handle = DBOS.retrieve_workflow(worker_id)
        try:
            return handle.get_result(polling_interval_sec=1.0)
        except Exception:
            current = DBOS.get_workflow_status(worker_id)
            if current is not None and current.status == "ERROR":
                return _recover_failed_workflow_tree(context, worker_id)
            raise
    finally:
        DBOS.destroy()


def _step_value(step: Any, key: str) -> Any:
    return step.get(key) if isinstance(step, dict) else getattr(step, key, None)


def _failed_workflow_step(workflow_id: str) -> tuple[int, str]:
    status = DBOS.get_workflow_status(workflow_id)
    if status is None or status.status != "ERROR":
        raise RuntimeError("recovery_source_workflow_is_not_error")
    steps = DBOS.list_workflow_steps(workflow_id)
    failed = [step for step in steps if _step_value(step, "error") is not None]
    if not failed:
        raise RuntimeError("recovery_failed_step_unavailable")
    selected = failed[-1]
    function_id = _step_value(selected, "function_id")
    function_name = _step_value(selected, "function_name")
    if not isinstance(function_id, int) or not isinstance(function_name, str):
        raise RuntimeError("recovery_failed_step_identity_unavailable")
    return function_id, function_name


def _fork_failed_workflow(
    source_workflow_id: str,
    fork_workflow_id: str,
    start_step: int,
    *,
    replacement_children: dict[str, str] | None = None,
) -> tuple[Any, bool]:
    existing = DBOS.get_workflow_status(fork_workflow_id)
    recovery_version = f"{DURABLE_APPARATUS_VERSION}-replication-recovery-001"
    if existing is not None:
        if existing.forked_from != source_workflow_id or existing.app_version != recovery_version:
            raise RuntimeError("recovery_fork_identity_mismatch")
        if existing.status == "ERROR":
            raise RuntimeError("recovery_fork_already_failed")
        return DBOS.retrieve_workflow(fork_workflow_id), False
    with SetWorkflowID(fork_workflow_id):
        handle = DBOS.fork_workflow(
            source_workflow_id,
            start_step,
            application_version=recovery_version,
            replacement_children=replacement_children,
        )
    if handle.workflow_id != fork_workflow_id:
        raise RuntimeError("recovery_fork_id_assignment_failed")
    return handle, True


def _recovery_index(journal: Path) -> int:
    if not journal.is_file():
        return 1
    indices = []
    for line in journal.read_text(encoding="utf-8").splitlines():
        try:
            indices.append(int(json.loads(line).get("recovery_index", 0)))
        except (ValueError, json.JSONDecodeError):
            continue
    return max(indices, default=0) + 1


def _write_recovery_event(journal: Path, record: dict[str, Any]) -> None:
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"timestamp": utc_now(), **record}, ensure_ascii=False, sort_keys=True) + "\n")


def _recover_failed_workflow_tree(context: DurableRuntimeContext, worker_workflow_id: str) -> dict[str, Any]:
    """Fork failed checkpoints, replacing failed Reviewer children without replaying committed results."""

    journal = context.run_root / "runtime" / "workflow_recovery.jsonl"
    recovery_index = _recovery_index(journal)
    worker_function_id, worker_function_name = _failed_workflow_step(worker_workflow_id)
    review_numbers = []
    snapshots = context.run_root / "reviewer" / "submission_snapshots"
    if snapshots.is_dir():
        for path in snapshots.glob("review_[0-9][0-9][0-9][0-9]"):
            try:
                review_numbers.append(int(path.name.removeprefix("review_")))
            except ValueError:
                continue
    failed_reviewers: list[tuple[str, int, str]] = []
    for number in sorted(review_numbers):
        workflow_id = f"{context.run_id}:reviewer:{number:04d}"
        status = DBOS.get_workflow_status(workflow_id)
        if status is not None and status.status == "ERROR":
            function_id, function_name = _failed_workflow_step(workflow_id)
            failed_reviewers.append((workflow_id, function_id, function_name))

    worker_attempts_before = context.store.provider_attempt_rows("worker")
    reviewer_attempts_before = context.store.provider_attempt_rows("reviewer")
    _write_recovery_event(journal, {
        "event": "RECOVERY_FORKS_REQUESTED",
        "recovery_index": recovery_index,
        "source_worker_workflow_id": worker_workflow_id,
        "source_worker_failed_function_id": worker_function_id,
        "source_worker_failed_function_name": worker_function_name,
        "source_worker_status_preserved": "ERROR",
        "worker_provider_attempt_count_before": len(worker_attempts_before),
        "worker_provider_attempts_sha256_before": sha256_json(worker_attempts_before),
        "reviewer_provider_attempt_count_before": len(reviewer_attempts_before),
        "reviewer_provider_attempts_sha256_before": sha256_json(reviewer_attempts_before),
        "source_reviewer_workflows": [
            {"workflow_id": workflow_id, "failed_function_id": function_id, "failed_function_name": function_name, "status_preserved": "ERROR"}
            for workflow_id, function_id, function_name in failed_reviewers
        ],
    })

    replacement_children: dict[str, str] = {}
    for reviewer_workflow_id, function_id, function_name in failed_reviewers:
        fork_id = f"{reviewer_workflow_id}:runtime_fork_{recovery_index:03d}"
        handle, created = _fork_failed_workflow(reviewer_workflow_id, fork_id, function_id)
        reviewer_result = handle.get_result(polling_interval_sec=1.0)
        status = DBOS.get_workflow_status(fork_id)
        if status is None or status.status != "SUCCESS":
            raise RuntimeError("recovered_reviewer_workflow_did_not_succeed")
        replacement_children[reviewer_workflow_id] = fork_id
        _write_recovery_event(journal, {
            "event": "REVIEWER_WORKFLOW_RECOVERED",
            "recovery_index": recovery_index,
            "source_workflow_id": reviewer_workflow_id,
            "source_failed_function_id": function_id,
            "source_failed_function_name": function_name,
            "fork_workflow_id": fork_id,
            "fork_created": created,
            "reviewer_result_status": reviewer_result.get("status"),
            "provider_attempt_count_after": context.store.provider_attempt_count("reviewer"),
        })

    worker_fork_id = f"{worker_workflow_id}:runtime_fork_{recovery_index:03d}"
    worker_handle, worker_created = _fork_failed_workflow(
        worker_workflow_id,
        worker_fork_id,
        worker_function_id,
        replacement_children=replacement_children or None,
    )
    result = worker_handle.get_result(polling_interval_sec=1.0)
    worker_attempts_after = context.store.provider_attempt_rows("worker")
    reviewer_attempts_after = context.store.provider_attempt_rows("reviewer")
    if worker_attempts_after[:len(worker_attempts_before)] != worker_attempts_before:
        raise RuntimeError("worker_fork_replayed_completed_provider_attempts")
    if reviewer_attempts_after[:len(reviewer_attempts_before)] != reviewer_attempts_before:
        raise RuntimeError("reviewer_fork_replayed_completed_provider_attempts")
    _write_recovery_event(journal, {
        "event": "WORKER_WORKFLOW_RECOVERED",
        "recovery_index": recovery_index,
        "source_workflow_id": worker_workflow_id,
        "source_failed_function_id": worker_function_id,
        "source_failed_function_name": worker_function_name,
        "fork_workflow_id": worker_fork_id,
        "fork_created": worker_created,
        "replacement_children": replacement_children,
        "termination_reason": result.get("termination_reason"),
        "provider_attempts_before": len(worker_attempts_before),
        "provider_attempts_after": len(worker_attempts_after),
    })
    return result


def run_durable_trajectory(
    repo_root: Path,
    *,
    run_id: str,
    condition: Condition,
    env_file: Path | None = None,
    image: str = DEFAULT_MINIMAL_IMAGE,
) -> dict[str, Any]:
    """Run a fresh independent trajectory; repeat the same command to resume DBOS state."""

    if not run_id or len(run_id) > 64 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for char in run_id):
        raise ValueError("invalid_durable_replication_run_id")
    repo_root = repo_root.resolve(strict=True)
    runs_root = (repo_root / RUNS_PARENT).resolve()
    run_root = runs_root / run_id
    if run_root.exists():
        manifest_path = run_root / "run_manifest.json"
        if not manifest_path.is_file():
            raise RuntimeError("partial_run_setup_preserved_but_not_resumable")
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("status") != "running":
            return {
                "status": existing.get("status"),
                "run_id": run_id,
                "run_root": run_root.as_posix(),
                "termination_reason": existing.get("termination_reason"),
                "artifact_hash_verification": verify_run_artifacts(run_root),
            }
        context, worker_provider, reviewer_provider, started_manifest = _load_existing_run(
            repo_root,
            run_root=run_root,
            run_id=run_id,
            condition=condition,
            env_file=env_file,
            image=image,
        )
    else:
        run_root, context, worker_provider, reviewer_provider = _prepare_fresh_run(
            repo_root,
            runs_root=runs_root,
            run_id=run_id,
            condition=condition,
            env_file=env_file,
            image=image,
        )
        started_manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))

    try:
        result = _run_dbos(context)
    except Exception as exc:
        error_path = run_root / "runtime" / "process_interruptions.jsonl"
        error_path.parent.mkdir(parents=True, exist_ok=True)
        with error_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"timestamp": utc_now(), "error_type": type(exc).__name__, "workflow_id": f"{run_id}:worker", "durable_state_preserved": True}, sort_keys=True) + "\n")
        raise

    context.store.checkpoint()
    with sqlite3.connect(run_root / "runtime" / "dbos.sqlite", timeout=30) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    manifest = _final_manifest(context, result, started_manifest)
    _write_json(run_root / "run_manifest.json", manifest)
    hashes = _artifact_hashes(run_root)
    _write_json(run_root / "artifact_hashes.json", hashes)
    verification = verify_run_artifacts(run_root)
    if verification["status"] != "passed":
        raise RuntimeError("new_run_artifact_hash_verification_failed; evidence_preserved")
    return {
        "status": manifest["status"],
        "run_id": run_id,
        "run_root": run_root.as_posix(),
        "condition": condition,
        "termination_reason": manifest["termination_reason"],
        "worker_model_responses": manifest["worker"]["model_responses"],
        "worker_tool_calls": manifest["worker"]["tool_calls"],
        "review_count": manifest["reviewer"]["review_count"],
        "artifact_hash_verification": verification,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--condition", choices=("worker_only", "explicit_collaboration"), required=True)
    parser.add_argument("--env-file", type=Path, help="Provider environment file; defaults to repository .env or process environment")
    parser.add_argument("--image", default=DEFAULT_MINIMAL_IMAGE)
    arguments = parser.parse_args(argv)
    result = run_durable_trajectory(
        arguments.repo_root,
        run_id=arguments.run_id,
        condition=arguments.condition,
        env_file=arguments.env_file,
        image=arguments.image,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
