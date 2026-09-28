from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.durable_store import DurableStore
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.durable_resume import _provider_env_file
from self_organizing_engineering_agent.experiments.ugs_synth_minimal.runner import SYSTEM_PROMPT
from self_organizing_engineering_agent.experiments.ugs_synth_minimal.tools import ALLOWED_TOOL_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).with_name("durable_process_harness.py")


def _run_harness(
    root: Path,
    scenario: str,
    *,
    crash_at: str | None = None,
    actor: str | None = None,
    turn: int | None = None,
    tool: str | None = None,
    review_number: int | None = None,
    legacy: bool = False,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None]:
    env = os.environ.copy()
    env.update({
        "DURABLE_TEST_SCENARIO": scenario,
        "DURABLE_TEST_SCALE_SLEEP": "1",
        "PYTHONPATH": str(REPO_ROOT / "src"),
    })
    for name, value in (
        ("DURABLE_TEST_CRASH_AT", crash_at),
        ("DURABLE_TEST_CRASH_ACTOR", actor),
        ("DURABLE_TEST_CRASH_TURN", str(turn) if turn is not None else None),
        ("DURABLE_TEST_CRASH_TOOL", tool),
        ("DURABLE_TEST_CRASH_REVIEW", str(review_number) if review_number is not None else None),
    ):
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    command = ["uv", "run", "--project", str(REPO_ROOT), "python", str(HARNESS), str(root)]
    if legacy:
        command.append("legacy")
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        return completed, None
    json_lines = [line for line in completed.stdout.splitlines() if line.startswith("{")]
    if not json_lines:
        return completed, None
    return completed, json.loads(json_lines[-1])


def _crash_then_resume(
    tmp_path: Path,
    scenario: str,
    *,
    crash_at: str,
    actor: str | None = None,
    turn: int | None = None,
    tool: str | None = None,
    review_number: int | None = None,
) -> dict[str, Any]:
    run_root = tmp_path / scenario
    first, _ = _run_harness(
        run_root,
        scenario,
        crash_at=crash_at,
        actor=actor,
        turn=turn,
        tool=tool,
        review_number=review_number,
    )
    assert first.returncode == 86, first.stdout + first.stderr
    second, summary = _run_harness(run_root, scenario)
    assert second.returncode == 0, second.stdout + second.stderr
    assert summary is not None, second.stdout + second.stderr
    return summary


def _tool_message_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: row[key] for key in ("role", "tool_call_id", "content") if key in row}
        for row in rows
    ]


def test_a_worker_response_five_commit_survives_process_kill(tmp_path: Path) -> None:
    result = _crash_then_resume(
        tmp_path,
        "worker_five_responses",
        crash_at="provider_response_committed",
        actor="worker",
        turn=5,
    )

    assert result["termination_reason"] == "agent_completed"
    assert result["worker_responses"] == 6
    assert result["provider_request_counts"] == {"worker": 6}
    assert result["tool_dispatch_counts"] == {"finish_project": 1}
    assert result["process_start_count"] == 2
    assistants = result["worker_assistant_messages"]
    assert [message.get("content") for message in assistants[:5]] == [
        "worker fragment 1", "worker fragment 2", "worker fragment 3", "worker fragment 4", "worker fragment 5",
    ]
    assert assistants[5]["tool_calls"][0]["function"]["name"] == "finish_project"


def test_b_request_intent_is_durable_before_provider_call(tmp_path: Path) -> None:
    result = _crash_then_resume(
        tmp_path,
        "provider_before_call",
        crash_at="before_provider_call",
        actor="worker",
        turn=1,
    )

    assert result["termination_reason"] == "agent_completed"
    assert result["provider_request_counts"] == {"worker": 1}
    assert result["provider_attempt_states"]["worker"] == ["SUCCEEDED"]
    assert result["worker_request_prepared_events"] == 1
    assert result["process_start_count"] == 2


def test_parent_no_response_request_is_marked_as_a_possible_duplicate(tmp_path: Path) -> None:
    process, result = _run_harness(tmp_path / "parent-unresolved", "parent_unresolved_duplicate")
    assert process.returncode == 0, process.stdout + process.stderr
    assert result is not None

    attempt = result["provider_attempts"]["worker"][0]
    assert attempt["possible_duplicate_provider_execution"] is True
    assert result["termination_reason"] == "agent_completed"


def test_c_external_dependency_suspension_resumes_same_turn(tmp_path: Path) -> None:
    run_root = tmp_path / "outage_then_recover"
    first, _ = _run_harness(
        run_root,
        "outage_then_recover",
        crash_at="durable_wait_started",
        actor="worker",
    )
    assert first.returncode == 86, first.stdout + first.stderr
    (run_root / "fake_provider_healthy.marker").write_text("healthy", encoding="ascii")
    second, result = _run_harness(run_root, "outage_then_recover")
    assert second.returncode == 0, second.stdout + second.stderr
    assert result is not None

    assert result["termination_reason"] == "agent_completed"
    assert result["suspensions"] == 1
    assert result["resumes"] == 1
    assert result["provider_request_counts"] == {"worker": 7}
    assert result["worker_responses"] == 1
    assert result["process_start_count"] == 2
    attempts = result["provider_attempts"]["worker"]
    assert len({row["request_id"] for row in attempts}) == 1
    assert len({row["request_hash"] for row in attempts}) == 1
    assert [row["logical_attempt"] for row in attempts] == list(range(1, 8))
    assert [row["state"] for row in attempts] == ["FAILED"] * 6 + ["SUCCEEDED"]


def test_worker_only_durable_run_keeps_baseline_prompt_and_tools(tmp_path: Path) -> None:
    process, result = _run_harness(tmp_path / "worker-only", "worker_only_finish")

    assert process.returncode == 0, process.stdout + process.stderr
    assert result is not None
    assert result["termination_reason"] == "agent_completed"
    assert result["review_count"] == 0
    assert result["reviewer_responses"] == 0
    assert result["reviewer_sandbox_present"] is False
    assert result["reviewer_directory_present"] is False
    assert result["provider_request_counts"] == {"worker": 1}
    assert result["worker_initial_messages"] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Complete the engineering project described in brief/ and provide the deliverables described there. You decide how to carry out the work and when it is complete."},
    ]
    assert result["worker_tool_names"] == list(ALLOWED_TOOL_NAMES)


def test_transport_outage_keeps_durably_retrying_after_backoff_schedule_is_exhausted(tmp_path: Path) -> None:
    run_root = tmp_path / "extended-outage"
    first, _ = _run_harness(
        run_root,
        "extended_outage_then_recover",
        crash_at="durable_wait_started",
        actor="worker",
    )
    assert first.returncode == 86, first.stdout + first.stderr

    second, result = _run_harness(run_root, "extended_outage_then_recover")
    assert second.returncode == 0, second.stdout + second.stderr
    assert result is not None
    assert result["termination_reason"] == "agent_completed"
    assert result["provider_request_counts"] == {"worker": 13}
    assert result["worker_responses"] == 1
    assert result["tool_dispatch_counts"] == {"finish_project": 1}
    assert result["process_start_count"] == 2
    assert result["resumes"] >= 6
    attempts = result["provider_attempts"]["worker"]
    assert [row["logical_attempt"] for row in attempts] == list(range(1, 14))
    assert [row["state"] for row in attempts] == ["FAILED"] * 12 + ["SUCCEEDED"]
    assert len({row["request_hash"] for row in attempts}) == 1


def test_d_reviewer_sixth_response_resumes_in_same_review(tmp_path: Path) -> None:
    result = _crash_then_resume(
        tmp_path,
        "review_mid_crash",
        crash_at="provider_response_committed",
        actor="reviewer",
        turn=6,
        review_number=1,
    )

    assert result["termination_reason"] == "agent_completed"
    assert result["review_count"] == 1
    assert result["reviewer_responses"] == 7
    assert result["provider_request_counts"] == {"reviewer": 7, "worker": 2}
    assert result["review_completed_events"] == 1
    assert result["process_start_count"] == 2
    reviewer_assistants = result["reviewer_assistant_messages"]
    assert [message.get("content") for message in reviewer_assistants[:6]] == [
        f"review fragment {index}" for index in range(1, 7)
    ]
    assert reviewer_assistants[6]["tool_calls"][0]["function"]["name"] == "finish_review"


def test_e_committed_review_reaches_worker_without_regeneration(tmp_path: Path) -> None:
    result = _crash_then_resume(
        tmp_path,
        "review_complete_before_worker",
        crash_at="reviewer_completed_before_worker_receives_review",
        review_number=1,
    )

    assert result["termination_reason"] == "agent_completed"
    assert result["review_count"] == 1
    assert result["provider_request_counts"] == {"reviewer": 1, "worker": 2}
    assert result["review_completed_events"] == 1
    assert result["process_start_count"] == 2


def test_f_committed_write_result_is_not_reexecuted(tmp_path: Path) -> None:
    result = _crash_then_resume(
        tmp_path,
        "tool_commit_crash",
        crash_at="tool_result_committed",
        actor="worker",
        tool="write_file",
    )

    assert result["termination_reason"] == "agent_completed"
    assert result["tool_dispatch_counts"] == {"finish_project": 1, "write_file": 1}
    assert result["tool_states"]["worker:worker-write-1"] == "COMMITTED"
    assert "replay.txt" in result["worker_project_files"]


def test_g_interrupted_python_side_effect_is_marked_uncertain(tmp_path: Path) -> None:
    result = _crash_then_resume(
        tmp_path,
        "python_uncertain_crash",
        crash_at="after_python_side_effect_before_observed",
        actor="worker",
        tool="execute_python",
    )

    assert result["termination_reason"] == "worker_tool_execution_uncertain"
    assert result["tool_dispatch_counts"] == {"execute_python": 1}
    assert result["tool_states"]["worker:worker-python-1"] == "TOOL_EXECUTION_STATE_UNCERTAIN"
    assert result["worker_project_files"]
    assert result["process_start_count"] == 2


def test_legacy_and_durable_protocol_behavior_are_equivalent(tmp_path: Path) -> None:
    legacy_root = tmp_path / "legacy"
    durable_root = tmp_path / "durable"
    legacy_process, legacy = _run_harness(legacy_root, "behavior_equivalence", legacy=True)
    durable_process, durable = _run_harness(durable_root, "behavior_equivalence")
    assert legacy_process.returncode == 0, legacy_process.stdout + legacy_process.stderr
    assert durable_process.returncode == 0, durable_process.stdout + durable_process.stderr
    assert legacy is not None and durable is not None

    assert legacy["termination_reason"] == durable["termination_reason"] == "agent_completed"
    assert legacy["provider_requests"] == durable["provider_requests"]
    assert legacy["worker_transcript"] == durable["worker_transcript"]
    assert legacy["reviewer_transcript"] == durable["reviewer_transcript"]
    assert _tool_message_rows(legacy["worker_tool_results"]) == _tool_message_rows(durable["worker_tool_results"])
    assert _tool_message_rows(legacy["reviewer_tool_results"]) == _tool_message_rows(durable["reviewer_tool_results"])
    assert legacy["worker_workspace"] == durable["worker_workspace"]
    assert legacy["reviewer_workspace"] == durable["reviewer_workspace"]
    assert legacy["formal_review"] == durable["formal_review"]


def test_worker_and_reviewer_multiple_tool_calls_use_the_same_assistant_message(tmp_path: Path) -> None:
    process, result = _run_harness(tmp_path / "multi-tool-response", "multi_tool_response")

    assert process.returncode == 0, process.stdout + process.stderr
    assert result is not None
    assert result["termination_reason"] == "agent_completed"
    assert result["worker_responses"] == 2
    assert result["reviewer_responses"] == 1
    assert [len(message.get("tool_calls") or []) for message in result["worker_assistant_messages"]] == [2, 1]
    assert [len(message.get("tool_calls") or []) for message in result["reviewer_assistant_messages"]] == [2]
    assert result["tool_states"]["worker:worker-submit-review-1"] == "COMMITTED"
    assert result["tool_states"]["worker:worker-write-1"] == "COMMITTED"
    assert result["tool_states"]["reviewer:review-write-1"] == "COMMITTED"
    assert result["tool_states"]["reviewer:review-finish-1"] == "COMMITTED"
    assert "worker-note.txt" in result["worker_project_files"]
    assert "reviewer-note.txt" in result["reviewer_project_files"]


def test_checkpoint_stabilizes_recovery_ledger_hash_after_reopen(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    first = DurableStore(runtime_root, run_id="checkpoint-test")
    first.append_evidence("worker/host_logs/messages.jsonl", "checkpoint-row", {"kind": "test_row"})
    first.checkpoint()
    initial_hash = hashlib.sha256((runtime_root / "recovery_ledger.sqlite").read_bytes()).hexdigest()

    reopened = DurableStore(runtime_root, run_id="checkpoint-test")
    rows = reopened.evidence("worker/host_logs/messages.jsonl")
    assert len(rows) == 1 and rows[0]["kind"] == "test_row"
    reopened.checkpoint()
    reopened_hash = hashlib.sha256((runtime_root / "recovery_ledger.sqlite").read_bytes()).hexdigest()

    assert reopened_hash == initial_hash


def test_resume_provider_environment_defaults_to_repository_dotenv(tmp_path: Path) -> None:
    local_env = tmp_path / ".env"
    local_env.touch()

    assert _provider_env_file(tmp_path, None) == local_env.resolve()


def test_resume_provider_environment_accepts_explicit_path_and_rejects_missing_file(tmp_path: Path) -> None:
    explicit_env = tmp_path / "config" / "provider.env"
    explicit_env.parent.mkdir()
    explicit_env.touch()

    assert _provider_env_file(tmp_path, explicit_env) == explicit_env.resolve()
    with pytest.raises(FileNotFoundError, match="provider_environment_file_missing"):
        _provider_env_file(tmp_path, tmp_path / "missing.env")
