from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from self_organizing_engineering_agent.experiments.pilot_1a.isolation import AgentSandbox
from self_organizing_engineering_agent.experiments.pilot_1a.provider import ProviderCallError
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review import runner
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.durable_runtime import (
    worker_tool_definitions_for_condition,
)
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.tools import (
    InterleavedReviewerExecutor,
    InterleavedReviewerTools,
    InterleavedWorkerTools,
    reviewer_tool_definitions,
    worker_tool_definitions,
)
from self_organizing_engineering_agent.experiments.ugs_synth_minimal.runner import (
    INITIAL_AGENT_PROMPT,
    SYSTEM_PROMPT,
)
from self_organizing_engineering_agent.experiments.ugs_synth_minimal.tools import (
    ALLOWED_TOOL_NAMES as BASE_WORKER_TOOL_NAMES,
    native_tool_definitions,
)


def _generation(
    name: str | None = None,
    arguments: dict[str, Any] | None = None,
    *,
    call_id: str = "call-1",
    finish_reason: str = "tool_calls",
    content: str = "",
    reasoning_content: str = "",
) -> SimpleNamespace:
    message: dict[str, Any] = {"role": "assistant", "content": content, "reasoning_content": reasoning_content}
    if name is not None:
        message["tool_calls"] = [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments or {}, ensure_ascii=False)},
            }
        ]
    return SimpleNamespace(
        assistant_message=message,
        usage={"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14, "reasoning_tokens": 2},
        returned_model="deepseek-flash",
        finish_reason=finish_reason,
        latency_sec=0.01,
        http_status=200,
    )


class SequenceProvider:
    model_id = "deepseek-flash"

    def __init__(self, generations: list[SimpleNamespace]) -> None:
        self.generations = list(generations)
        self.requests: list[dict[str, Any]] = []

    def generate_with_native_tools(self, messages, tools, *, max_output_tokens):  # type: ignore[no-untyped-def]
        self.requests.append({"messages": [dict(message) for message in messages], "tools": tools, "max_output_tokens": max_output_tokens})
        return self.generations.pop(0)


def _review_result(label: str) -> dict[str, Any]:
    return {
        "summary": f"Formal summary {label}.",
        "findings": [
            {
                "finding_id": "F-001",
                "status": "observation",
                "severity": "low",
                "confidence": "high",
                "claim_challenged": "A documented claim.",
                "public_basis": "The public brief.",
                "evidence": f"Visible evidence for {label}.",
                "why_it_matters": "The evidence bounds the claim.",
            }
        ],
    }


def test_worker_surface_adds_only_submit_and_explicitly_describes_voluntary_review() -> None:
    base = native_tool_definitions()
    treatment = worker_tool_definitions()
    assert [row["function"]["name"] for row in treatment] == [*BASE_WORKER_TOOL_NAMES, "submit_for_review"]
    assert treatment[:-1] == base
    assert SYSTEM_PROMPT.endswith("A normal text response does not by itself mark the project complete.")
    expected_statement = """You have access to an independent Reviewer through `submit_for_review`.

The Reviewer can examine the current project state and provide independent critical feedback. You may request a review whenever you judge it useful.

You decide whether to use the Reviewer, when to request review, what to ask it to focus on, and how to respond to its findings."""
    assert runner.WORKER_REVIEWER_CAPABILITY_STATEMENT == expected_statement
    assert runner.WORKER_SYSTEM_PROMPT == f"{SYSTEM_PROMPT}\n\n{expected_statement}"
    assert "finish_project" in runner.WORKER_SYSTEM_PROMPT
    prompt_lower = runner.WORKER_SYSTEM_PROMPT.lower()
    for forbidden in (
        "mandatory review",
        "review every n turns",
        "review regularly",
        "milestone review",
        "review before finish_project",
        "review at least once",
        "review until no findings remain",
        "resolve every finding",
        "follow reviewer recommendations",
    ):
        assert forbidden not in prompt_lower
    assert INITIAL_AGENT_PROMPT == "Complete the engineering project described in brief/ and provide the deliverables described there. You decide how to carry out the work and when it is complete."


def test_durable_worker_only_surface_is_identical_to_the_frozen_minimal_baseline() -> None:
    base = native_tool_definitions()
    treatment = worker_tool_definitions()

    assert worker_tool_definitions_for_condition(False) == base
    assert [row["function"]["name"] for row in worker_tool_definitions_for_condition(False)] == list(BASE_WORKER_TOOL_NAMES)
    assert worker_tool_definitions_for_condition(True) == treatment
    assert [row["function"]["name"] for row in reviewer_tool_definitions()] == [
        "list_files",
        "read_file",
        "write_file",
        "execute_python",
        "finish_review",
    ]


def test_reviewer_workspace_scopes_files_and_python_paths(tmp_path: Path) -> None:
    agent_view = tmp_path / "review-agent"
    brief = agent_view / "brief"
    review = agent_view / "review"
    submission = tmp_path / "snapshot"
    brief.mkdir(parents=True)
    review.mkdir()
    submission.mkdir()
    (brief / "brief.md").write_text("public", encoding="utf-8")
    (review / "notes.txt").write_text("private analysis", encoding="utf-8")
    (submission / "report.md").write_text("submitted report", encoding="utf-8")
    sandbox = AgentSandbox(tmp_path, agent_view, brief, review)
    executor = InterleavedReviewerExecutor(
        image="test-image",
        brief_root=brief,
        project_root=review,
        submission_root=submission,
    )
    tools = InterleavedReviewerTools(
        sandbox=sandbox,
        executor=executor,
        review_number=1,
        snapshot_root=submission,
        record_formal_review=lambda _number, _result: "hash",
    )

    assert tools.list_files()["files"] == ["brief/brief.md", "review/notes.txt", "submission/report.md"]
    assert tools.read_file("submission/report.md")["content"] == "submitted report"
    assert "tool_error" in tools.write_file("submission/report.md", "changed")
    assert "tool_error" in tools.write_file("brief/brief.md", "changed")
    assert tools.write_file("review/new.txt", "review output")["bytes"] == len("review output")
    assert "tool_error" in tools.execute_python({"path": "submission/report.md"})


def test_interleaved_reviews_keep_private_reviewer_context_and_return_only_formal_findings(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    worker_project = run_root / "worker_project"
    worker_project.mkdir()
    reviewer_agent = run_root / "reviewer_agent"
    reviewer_brief = reviewer_agent / "brief"
    reviewer_workspace = reviewer_agent / "review"
    reviewer_brief.mkdir(parents=True)
    reviewer_workspace.mkdir()
    (reviewer_brief / "brief.md").write_text("public project objective", encoding="utf-8")
    reviewer_sandbox = AgentSandbox(run_root, reviewer_agent, reviewer_brief, reviewer_workspace)
    instrumentation = runner.RunInstrumentation(run_root)

    first_formal = _review_result("first")
    second_formal = _review_result("second")
    reviewer_provider = SequenceProvider(
        [
            _generation(finish_reason="length", reasoning_content="reviewer-private-reasoning"),
            _generation("finish_review", first_formal, call_id="review-finish-1"),
            _generation("finish_review", second_formal, call_id="review-finish-2"),
        ]
    )
    reviewer = runner.InterleavedReviewSession(
        provider=reviewer_provider,
        sandbox=reviewer_sandbox,
        image="test-image",
        reviewer_root=run_root / "reviewer",
        instrumentation=instrumentation,
    )
    source_project = worker_project
    (source_project / "reports").mkdir()
    (source_project / "reports" / "report.md").write_text("state one", encoding="utf-8")

    def review_callback(note: str) -> dict[str, Any]:
        review_number = callback_state["count"] + 1
        callback_state["count"] = review_number
        snapshot = run_root / "snapshots" / f"review_{review_number:04d}"
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        info = runner._freeze_submission(source_project, snapshot)
        result = reviewer.review(note, review_number=review_number, snapshot_root=snapshot, snapshot_info=info)
        return {key: result[key] for key in ("review_number", "summary", "findings") if key in result}

    callback_state = {"count": 0}

    class BaseTools:
        sandbox = SimpleNamespace(project_root=worker_project)

        def dispatch(self, name, arguments):  # type: ignore[no-untyped-def]
            if name == "write_file":
                relative = arguments["path"].removeprefix("project/")
                target = worker_project / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(arguments["content"], encoding="utf-8")
                return {"path": arguments["path"]}
            if name == "finish_project":
                return {"status": "finish_requested"}
            raise AssertionError(name)

    worker_provider = SequenceProvider(
        [
            _generation("submit_for_review", {}, call_id="worker-review-1", reasoning_content="worker-private-reasoning"),
            _generation("write_file", {"path": "project/reports/report.md", "content": "state two"}, call_id="worker-write-2"),
            _generation("submit_for_review", {"note": "Look at the new report."}, call_id="worker-review-2"),
            _generation("finish_project", {}, call_id="worker-finish"),
        ]
    )
    worker_tools = InterleavedWorkerTools(BaseTools(), review_callback)
    result = runner._run_worker(worker_provider, worker_tools, instrumentation)

    assert result["termination_reason"] == "agent_completed"
    assert result["submit_for_review_calls"] == 2
    assert len(reviewer.messages) > 2
    assert sum(message.get("role") == "system" for message in reviewer.messages) == 1
    assert "reviewer-private-reasoning" in json.dumps(reviewer.messages, ensure_ascii=False)
    assert reviewer_provider.requests[1]["messages"][-1]["reasoning_content"] == "reviewer-private-reasoning"
    worker_context = json.dumps(worker_provider.requests, ensure_ascii=False)
    assert "reviewer-private-reasoning" not in worker_context
    assert "worker-private-reasoning" not in json.dumps(reviewer_provider.requests, ensure_ascii=False)
    worker_tool_results = [message["content"] for request in worker_provider.requests for message in request["messages"] if message.get("role") == "tool"]
    assert any("Formal summary first." in content for content in worker_tool_results)
    assert any("Formal summary second." in content for content in worker_tool_results)
    assert "reviewer-private-reasoning" not in "\n".join(worker_tool_results)
    assert (run_root / "snapshots" / "review_0001" / "reports" / "report.md").read_text(encoding="utf-8") == "state one"
    assert (run_root / "snapshots" / "review_0002" / "reports" / "report.md").read_text(encoding="utf-8") == "state two"


def test_worker_reasoning_only_length_response_is_replayed_before_finish(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first_response = _generation(finish_reason="length", reasoning_content="worker-continuation-sentinel")
    provider = SequenceProvider(
        [
            first_response,
            _generation("finish_project", {}, call_id="worker-finish"),
        ]
    )

    class BaseTools:
        sandbox = SimpleNamespace(project_root=project)

        def dispatch(self, name, arguments):  # type: ignore[no-untyped-def]
            return {"status": "finish_requested"}

    instrumentation = runner.RunInstrumentation(tmp_path / "run")
    result = runner._run_worker(provider, InterleavedWorkerTools(BaseTools(), lambda _note: {}), instrumentation)
    assert result["termination_reason"] == "agent_completed"
    replayed = provider.requests[1]["messages"][-1]
    assert replayed == first_response.assistant_message
    assert replayed["reasoning_content"] == "worker-continuation-sentinel"
    assert result["length_continuations"] == 1


def test_five_transport_retries_recover_on_sixth_attempt_and_log_schedule(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    delays: list[float] = []
    monkeypatch.setattr(runner.time, "sleep", delays.append)
    instrumentation = runner.RunInstrumentation(tmp_path / "retry-run")

    class TransientProvider:
        def __init__(self) -> None:
            self.calls = 0
            self.message_objects: list[list[dict[str, Any]]] = []

        def generate_with_native_tools(self, messages, _tools, *, max_output_tokens):  # type: ignore[no-untyped-def]
            self.calls += 1
            self.message_objects.append(messages)
            assert max_output_tokens == runner.MAX_OUTPUT_TOKENS
            if self.calls <= 5:
                raise ProviderCallError({"category": "provider_transport_error", "error_type": "RemoteDisconnected", "http_status": None})
            return _generation("finish_project", {}, call_id="finish-after-five-retries")

    provider = TransientProvider()
    result = runner._generate_with_transport_retry(
        provider,
        [],
        worker_tool_definitions(),
        max_output_tokens=runner.MAX_OUTPUT_TOKENS,
        instrumentation=instrumentation,
        role="worker",
        turn=1,
    )
    assert result.returned_model == "deepseek-flash"
    assert provider.calls == runner.MAX_PROVIDER_TOTAL_ATTEMPTS == 6
    assert all(messages is provider.message_objects[0] for messages in provider.message_objects)
    assert instrumentation.worker_provider_attempts == 6
    assert instrumentation.worker_transport_retries == 5
    assert delays == [2, 5, 10, 20, 30]
    log_rows = [
        json.loads(line)
        for line in (tmp_path / "retry-run" / "worker" / "host_logs" / "messages.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    attempt_rows = [row for row in log_rows if row.get("kind") == "provider_request_attempt"]
    retry_rows = [row for row in log_rows if row.get("kind") == "provider_transport_retry"]
    assert [row["attempt"] for row in attempt_rows] == [1, 2, 3, 4, 5, 6]
    assert [row["retry_delay_sec"] for row in retry_rows] == [2, 5, 10, 20, 30]
    assert all(row["possible_duplicate_provider_execution"] is True for row in retry_rows)


def test_transport_retry_exhaustion_stops_after_six_total_attempts(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    delays: list[float] = []
    monkeypatch.setattr(runner.time, "sleep", delays.append)
    instrumentation = runner.RunInstrumentation(tmp_path / "exhausted-run")

    class AlwaysUnavailableProvider:
        calls = 0

        def generate_with_native_tools(self, _messages, _tools, *, max_output_tokens):  # type: ignore[no-untyped-def]
            self.calls += 1
            raise ProviderCallError({"category": "provider_transport_error", "error_type": "URLError", "http_status": None})

    provider = AlwaysUnavailableProvider()
    with pytest.raises(ProviderCallError):
        runner._generate_with_transport_retry(
            provider,
            [],
            worker_tool_definitions(),
            max_output_tokens=runner.MAX_OUTPUT_TOKENS,
            instrumentation=instrumentation,
            role="worker",
            turn=1,
        )

    assert provider.calls == runner.MAX_PROVIDER_TOTAL_ATTEMPTS == 6
    assert instrumentation.worker_provider_attempts == 6
    assert instrumentation.worker_transport_retries == 5
    assert delays == [2, 5, 10, 20, 30]
    log_rows = [
        json.loads(line)
        for line in (tmp_path / "exhausted-run" / "worker" / "host_logs" / "messages.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len([row for row in log_rows if row.get("kind") == "provider_request_attempt"]) == 6
    assert len([row for row in log_rows if row.get("kind") == "provider_transport_retry"]) == 5


def test_worker_provider_request_contains_treatment_prompt(tmp_path: Path) -> None:
    provider = SequenceProvider([_generation("finish_project", {}, call_id="finish-prompt-check")])

    class BaseTools:
        sandbox = SimpleNamespace(project_root=tmp_path / "project")

        def dispatch(self, _name, _arguments):  # type: ignore[no-untyped-def]
            return {"status": "finish_requested"}

    BaseTools.sandbox.project_root.mkdir()
    runner._run_worker(
        provider,
        InterleavedWorkerTools(BaseTools(), lambda _note: {}),
        runner.RunInstrumentation(tmp_path / "prompt-run"),
    )
    assert provider.requests[0]["messages"][0] == {"role": "system", "content": runner.WORKER_SYSTEM_PROMPT}


def test_provider_retries_only_no_http_transport_errors(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(runner.time, "sleep", lambda _delay: None)

    class ErrorProvider:
        def __init__(self, details: dict[str, Any]) -> None:
            self.details = details
            self.calls = 0

        def generate_with_native_tools(self, _messages, _tools, *, max_output_tokens):  # type: ignore[no-untyped-def]
            self.calls += 1
            raise ProviderCallError(self.details)

    non_transport_errors = [
        {"category": "provider_http_error", "error_type": "HTTPError", "http_status": 400},
        {"category": "provider_http_error", "error_type": "HTTPError", "http_status": 503},
        {"category": "provider_parse_error", "error_type": "invalid_json_response", "http_status": 200},
    ]
    for index, details in enumerate(non_transport_errors, start=1):
        provider = ErrorProvider(details)
        with pytest.raises(ProviderCallError):
            runner._generate_with_transport_retry(
                provider,
                [],
                worker_tool_definitions(),
                max_output_tokens=runner.MAX_OUTPUT_TOKENS,
                instrumentation=runner.RunInstrumentation(tmp_path / f"non-transport-{index}"),
                role="worker",
                turn=index,
            )
        assert provider.calls == 1

    class EmptyStopProvider:
        calls = 0

        def generate_with_native_tools(self, _messages, _tools, *, max_output_tokens):  # type: ignore[no-untyped-def]
            self.calls += 1
            return _generation(finish_reason="stop", content="")

    empty_stop_provider = EmptyStopProvider()
    generation = runner._generate_with_transport_retry(
        empty_stop_provider,
        [],
        worker_tool_definitions(),
        max_output_tokens=runner.MAX_OUTPUT_TOKENS,
        instrumentation=runner.RunInstrumentation(tmp_path / "empty-stop"),
        role="worker",
        turn=10,
    )
    assert generation.finish_reason == "stop"
    assert empty_stop_provider.calls == 1
