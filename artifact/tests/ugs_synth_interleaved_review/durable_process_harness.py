from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError

from dbos import DBOS, SetWorkflowID

from self_organizing_engineering_agent.experiments.pilot_1a.provider import ProviderCallError
from self_organizing_engineering_agent.experiments.pilot_1a.isolation import AgentSandbox
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.durable_runtime import (
    DurableProviderBoundaryLogger,
    DurableRuntimeContext,
    _request_hash,
    _worker_workflow,
    configure_runtime,
)
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.durable_store import (
    DurableStore,
)
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.tools import worker_tool_definitions
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.runner import (
    INITIAL_AGENT_PROMPT,
    REVIEWER_INITIAL_PROMPT,
    REVIEWER_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    WORKER_SYSTEM_PROMPT,
)


class DeterministicProvider:
    model_id = "deepseek-flash"
    configured_model = "deepseek-flash"
    effective_model = "deepseek-flash"
    provider_name = "deterministic test provider"
    base_url = "https://test.invalid"
    thinking = "enabled"
    reasoning_effort = "high"
    timeout_sec = 5.0

    def __init__(self, actor: str, state_path: Path, health_path: Path) -> None:
        self.actor = actor
        self.state_path = state_path
        self.health_path = health_path
        self._context: dict[str, object] = {}

    def set_boundary_context(self, context: dict[str, object]) -> None:
        self._context = dict(context)

    def build_native_tool_request_payload(self, messages, tools, *, max_output_tokens):
        return {
            "model": self.effective_model,
            "messages": messages,
            "reasoning_effort": self.reasoning_effort,
            "thinking": {"type": self.thinking},
            "max_tokens": max_output_tokens,
            "tools": tools,
            "tool_choice": "auto",
        }

    def _record_request(self, messages, tools, max_output_tokens):
        request = self.build_native_tool_request_payload(messages, tools, max_output_tokens=max_output_tokens)
        request_bytes = json.dumps(request, ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(request_bytes).hexdigest()
        with sqlite3.connect(self.state_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS provider_requests (actor TEXT, request_hash TEXT, request_body TEXT, count INTEGER, PRIMARY KEY(actor,request_hash))"
            )
            row = connection.execute(
                "SELECT count FROM provider_requests WHERE actor=? AND request_hash=?", (self.actor, digest)
            ).fetchone()
            count = (row[0] if row else 0) + 1
            connection.execute(
                "INSERT INTO provider_requests(actor,request_hash,request_body,count) VALUES(?,?,?,?) "
                "ON CONFLICT(actor,request_hash) DO UPDATE SET count=excluded.count,request_body=excluded.request_body",
                (self.actor, digest, request_bytes.decode("utf-8"), count),
            )
        return digest

    def _assistant(self, messages, *, finish_reason="stop", calls=None, content="", reasoning=""):
        # This ordering deliberately matches the direct provider adapter's assistant history shape.
        message = {"role": "assistant", "content": content, "reasoning_content": reasoning}
        if calls is not None:
            message["tool_calls"] = calls
        return SimpleNamespace(
            assistant_message=message,
            usage={"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
            returned_model="deepseek-flash",
            finish_reason=finish_reason,
            latency_sec=0.001,
            http_status=200,
        )

    def generate_with_native_tools(self, messages, tools, *, max_output_tokens):
        request_hash = self._record_request(messages, tools, max_output_tokens)
        turn = sum(1 for message in messages if message.get("role") == "assistant") + 1
        scenario = os.environ["DURABLE_TEST_SCENARIO"]
        if scenario == "extended_outage_then_recover" and self.actor == "worker":
            with sqlite3.connect(self.state_path) as connection:
                attempts = connection.execute(
                    "SELECT count FROM provider_requests WHERE actor=? AND request_hash=?",
                    (self.actor, request_hash),
                ).fetchone()[0]
            if attempts <= 12:
                try:
                    raise URLError("simulated prolonged no-response outage")
                except URLError as cause:
                    raise ProviderCallError({
                        "error_type": "URLError",
                        "category": "provider_transport_error",
                        "http_status": None,
                    }) from cause
        if scenario == "outage_then_recover" and self.actor == "worker" and not self.health_path.exists():
            try:
                raise URLError("simulated no-response outage")
            except URLError as cause:
                raise ProviderCallError({
                    "error_type": "URLError",
                    "category": "provider_transport_error",
                    "http_status": None,
                }) from cause
        if self.actor == "reviewer":
            if scenario == "review_mid_crash" and turn <= 6:
                return self._assistant(messages, finish_reason="length", content=f"review fragment {turn}", reasoning="review reasoning")
            formal = {"summary": "deterministic review", "findings": []}
            if scenario == "multi_tool_response":
                return self._assistant(messages, finish_reason="tool_calls", calls=[
                    {
                        "id": "review-write-1",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps({"path": "review/reviewer-note.txt", "content": "review note"}),
                        },
                    },
                    {
                        "id": "review-finish-1",
                        "type": "function",
                        "function": {"name": "finish_review", "arguments": json.dumps(formal, ensure_ascii=False)},
                    },
                ])
            return self._assistant(messages, finish_reason="tool_calls", calls=[{
                "id": "review-finish-1",
                "type": "function",
                "function": {"name": "finish_review", "arguments": json.dumps(formal, ensure_ascii=False)},
            }])

        if scenario == "worker_five_responses" and turn <= 5:
            return self._assistant(messages, finish_reason="length", content=f"worker fragment {turn}", reasoning="worker reasoning")
        if scenario in {"review_mid_crash", "review_complete_before_worker"} and turn == 1:
            return self._assistant(messages, finish_reason="tool_calls", calls=[{
                "id": "worker-submit-review-1",
                "type": "function",
                "function": {"name": "submit_for_review", "arguments": json.dumps({"note": "test review"})},
            }])
        if scenario == "tool_commit_crash" and turn == 1:
            args = {"path": "replay.txt", "content": "stable write"}
            return self._assistant(messages, finish_reason="tool_calls", calls=[{
                "id": "worker-write-1", "type": "function",
                "function": {"name": "write_file", "arguments": json.dumps(args)},
            }])
        if scenario == "python_uncertain_crash" and turn == 1:
            args = {"code": "print('simulated')"}
            return self._assistant(messages, finish_reason="tool_calls", calls=[{
                "id": "worker-python-1", "type": "function",
                "function": {"name": "execute_python", "arguments": json.dumps(args)},
            }])
        if scenario == "multi_tool_response" and turn == 1:
            return self._assistant(messages, finish_reason="tool_calls", calls=[
                {
                    "id": "worker-submit-review-1",
                    "type": "function",
                    "function": {"name": "submit_for_review", "arguments": json.dumps({"note": "test review"})},
                },
                {
                    "id": "worker-write-1",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": json.dumps({"path": "worker-note.txt", "content": "worker note"}),
                    },
                },
            ])
        if scenario == "provider_before_call" or scenario in {"worker_five_responses", "tool_commit_crash", "review_complete_before_worker"}:
            return self._finish_call(turn)
        if scenario == "outage_then_recover":
            return self._finish_call(turn)
        if scenario == "behavior_equivalence" and turn == 1:
            return self._assistant(messages, finish_reason="tool_calls", calls=[{
                "id": "worker-submit-review-1",
                "type": "function",
                "function": {"name": "submit_for_review", "arguments": json.dumps({"note": "test review"})},
            }])
        return self._finish_call(turn)

    def _finish_call(self, turn: int):
        return self._assistant(messages=[], finish_reason="tool_calls", calls=[{
            "id": f"worker-finish-{turn}",
            "type": "function",
            "function": {"name": "finish_project", "arguments": "{}"},
        }])


class CountingWorkerTools:
    def __init__(self, project_root: Path, state_path: Path) -> None:
        self.project_root = project_root
        self.state_path = state_path
        self.sandbox = SimpleNamespace(project_root=project_root)

    def dispatch(self, name, arguments):
        with sqlite3.connect(self.state_path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS tool_dispatches (name TEXT PRIMARY KEY, count INTEGER NOT NULL)")
            connection.execute(
                "INSERT INTO tool_dispatches(name,count) VALUES(?,1) ON CONFLICT(name) DO UPDATE SET count=count+1",
                (name,),
            )
        if name == "write_file":
            target = self.project_root / arguments["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(arguments["content"], encoding="utf-8", newline="")
            return {"path": arguments["path"], "bytes": len(arguments["content"].encode("utf-8"))}
        if name == "execute_python":
            (self.project_root / "python_side_effect.txt").write_text("executed", encoding="utf-8")
            return {"status": "completed", "exit_code": 0, "stdout": "", "stderr": "", "timeout": False}
        if name == "finish_project":
            return {"status": "finish_requested"}
        return {"status": "ok", "tool": name}


def _crash_hook(root: Path):
    target = os.environ.get("DURABLE_TEST_CRASH_AT", "")
    if not target:
        return None
    target_actor = os.environ.get("DURABLE_TEST_CRASH_ACTOR", "")
    target_turn = os.environ.get("DURABLE_TEST_CRASH_TURN", "")
    target_tool = os.environ.get("DURABLE_TEST_CRASH_TOOL", "")
    target_review = os.environ.get("DURABLE_TEST_CRASH_REVIEW", "")
    marker_root = root / "runtime" / "crash_markers"
    marker_root.mkdir(parents=True, exist_ok=True)

    def hook(name, details):
        if name != target:
            return
        if target_actor and details.get("actor") != target_actor:
            return
        if target_turn and str(details.get("turn")) != target_turn:
            return
        if target_tool and details.get("tool") != target_tool:
            return
        if target_review and str(details.get("review_number")) != target_review:
            return
        identity = hashlib.sha256(json.dumps([name, details], sort_keys=True).encode()).hexdigest()
        marker = marker_root / f"{identity}.marker"
        if marker.exists():
            return
        marker.write_text("killed", encoding="ascii")
        os._exit(86)

    return hook


def _request_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with sqlite3.connect(path) as connection:
        return [
            {"actor": actor, "request_hash": digest, "request_body": body, "count": count}
            for actor, digest, body, count in connection.execute(
                "SELECT actor,request_hash,request_body,count FROM provider_requests ORDER BY rowid"
            )
        ]


def _workspace_files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _reviewer_workspace_files(root: Path) -> dict[str, str]:
    files = _workspace_files(root)
    history = root / "review_history.jsonl"
    if history.is_file():
        normalized = []
        for line in history.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            row.pop("timestamp", None)
            normalized.append(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        files["review_history.jsonl"] = hashlib.sha256(("\n".join(normalized) + "\n").encode("utf-8")).hexdigest()
    return files


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _legacy_main(root: Path) -> int:
    from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review import runner
    from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.tools import InterleavedWorkerTools
    from self_organizing_engineering_agent.experiments.pilot_1a.isolation import AgentSandbox

    # Both runtimes receive the same stable clock so formal-review evidence is byte-comparable.
    runner.utc_now = lambda: "2030-01-02T03:04:05Z"
    (root / "worker" / "sandbox" / "agent_view" / "brief").mkdir(parents=True, exist_ok=True)
    worker_project = root / "worker" / "sandbox" / "agent_view" / "project"
    worker_project.mkdir(parents=True, exist_ok=True)
    reviewer_agent = root / "reviewer" / "sandbox" / "agent_view"
    reviewer_brief = reviewer_agent / "brief"
    reviewer_workspace = reviewer_agent / "review"
    reviewer_brief.mkdir(parents=True, exist_ok=True)
    reviewer_workspace.mkdir(parents=True, exist_ok=True)
    (root / "reviewer" / "submission_snapshots").mkdir(parents=True, exist_ok=True)
    state_path = root / "runtime" / "fake_state.sqlite"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    worker_sandbox = AgentSandbox(
        run_root=(root / "worker" / "sandbox").resolve(),
        agent_view=(root / "worker" / "sandbox" / "agent_view").resolve(),
        brief_root=(root / "worker" / "sandbox" / "agent_view" / "brief").resolve(),
        project_root=worker_project.resolve(),
    )
    reviewer_sandbox = AgentSandbox(
        run_root=(root / "reviewer" / "sandbox").resolve(),
        agent_view=reviewer_agent.resolve(),
        brief_root=reviewer_brief.resolve(),
        project_root=reviewer_workspace.resolve(),
    )
    health = root / "fake_provider_healthy.marker"
    instrumentation = runner.RunInstrumentation(root)
    reviewer_provider = DeterministicProvider("reviewer", state_path, health)
    reviewer = runner.InterleavedReviewSession(
        provider=reviewer_provider,
        sandbox=reviewer_sandbox,
        image="test:durable",
        reviewer_root=root / "reviewer",
        instrumentation=instrumentation,
    )
    review_count = 0

    def request_review(note: str) -> dict[str, object]:
        nonlocal review_count
        review_count += 1
        snapshot_root = root / "reviewer" / "submission_snapshots" / f"review_{review_count:04d}"
        snapshot = runner._freeze_submission(worker_project, snapshot_root)
        result = reviewer.review(note, review_number=review_count, snapshot_root=snapshot_root, snapshot_info=snapshot)
        return {key: result[key] for key in ("review_number", "summary", "findings") if key in result}

    worker_provider = DeterministicProvider("worker", state_path, health)
    worker_tools = InterleavedWorkerTools(CountingWorkerTools(worker_project, state_path), request_review)
    result = runner._run_worker(worker_provider, worker_tools, instrumentation)
    summary = {
        "termination_reason": result["termination_reason"],
        "provider_requests": _request_rows(state_path),
        "worker_transcript": [
            {"role": "system", "content": runner.WORKER_SYSTEM_PROMPT},
            {"role": "user", "content": runner.INITIAL_AGENT_PROMPT},
            *[
                row["assistant_message"] if row.get("kind") == "model_response" else
                {key: row[key] for key in ("role", "tool_call_id", "content") if key in row}
                for row in _read_jsonl(root / "worker" / "host_logs" / "messages.jsonl")
                if row.get("kind") in {"model_response", "tool_result"}
            ],
        ],
        "reviewer_transcript": reviewer.messages,
        "worker_workspace": _workspace_files(worker_project),
        "reviewer_workspace": _reviewer_workspace_files(reviewer_workspace),
        "worker_tool_results": [
            message for message in _read_jsonl(root / "worker" / "host_logs" / "messages.jsonl")
            if message.get("kind") == "tool_result"
        ],
        "reviewer_tool_results": [
            message for message in _read_jsonl(root / "reviewer" / "host_logs" / "messages.jsonl")
            if message.get("kind") == "tool_result"
        ],
        "formal_review": json.loads((root / "reviewer" / "reviews" / "review_0001" / "formal_review.json").read_text(encoding="utf-8")),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 2 and sys.argv[2] == "legacy":
        return _legacy_main(root)
    runtime = root / "runtime"
    runtime.mkdir(exist_ok=True)
    (root / "worker" / "sandbox" / "agent_view" / "brief").mkdir(parents=True, exist_ok=True)
    project = root / "worker" / "sandbox" / "agent_view" / "project"
    project.mkdir(parents=True, exist_ok=True)
    reviewer_enabled = os.environ["DURABLE_TEST_SCENARIO"] != "worker_only_finish"
    reviewer_brief = root / "reviewer" / "sandbox" / "agent_view" / "brief"
    review = root / "reviewer" / "sandbox" / "agent_view" / "review"
    if reviewer_enabled:
        reviewer_brief.mkdir(parents=True, exist_ok=True)
        review.mkdir(parents=True, exist_ok=True)
        (root / "reviewer" / "submission_snapshots").mkdir(parents=True, exist_ok=True)
    health = root / "fake_provider_healthy.marker"
    fake_state = runtime / "fake_state.sqlite"
    run_id = "durable-test-" + os.environ["DURABLE_TEST_SCENARIO"]
    store = DurableStore(runtime, run_id=run_id)
    worker_sandbox = AgentSandbox(
        run_root=(root / "worker" / "sandbox").resolve(),
        agent_view=(root / "worker" / "sandbox" / "agent_view").resolve(),
        brief_root=(root / "worker" / "sandbox" / "agent_view" / "brief").resolve(),
        project_root=project.resolve(),
    )
    reviewer_sandbox = (
        AgentSandbox(
            run_root=(root / "reviewer" / "sandbox").resolve(),
            agent_view=(root / "reviewer" / "sandbox" / "agent_view").resolve(),
            brief_root=reviewer_brief.resolve(),
            project_root=review.resolve(),
        )
        if reviewer_enabled
        else None
    )
    worker_provider = DeterministicProvider("worker", fake_state, health)
    reviewer_provider = DeterministicProvider("reviewer", fake_state, health) if reviewer_enabled else None
    boundary = DurableProviderBoundaryLogger(root, run_id, store)
    context = DurableRuntimeContext(
        run_root=root,
        run_id=run_id,
        worker_provider=worker_provider,
        reviewer_provider=reviewer_provider,
        worker_tools=CountingWorkerTools(project, fake_state),
        worker_sandbox=worker_sandbox,
        reviewer_sandbox=reviewer_sandbox,
        image="test:durable",
        store=store,
        boundary_logger=boundary,
        crash_hook=_crash_hook(root),
        reviewer_enabled=reviewer_enabled,
    )
    if os.environ["DURABLE_TEST_SCENARIO"] == "behavior_equivalence":
        import self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.durable_runtime as durable_runtime
        durable_runtime.utc_now = lambda: "2030-01-02T03:04:05Z"
    configure_runtime(context)
    if store.conversation_count("worker") == 0:
        scenario = os.environ["DURABLE_TEST_SCENARIO"]
        worker_initial = (
            {"role": "system", "content": WORKER_SYSTEM_PROMPT},
            {"role": "user", "content": INITIAL_AGENT_PROMPT},
        ) if scenario == "behavior_equivalence" else (
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": INITIAL_AGENT_PROMPT},
        ) if scenario == "worker_only_finish" else (
            {"role": "system", "content": "test worker system"},
            {"role": "user", "content": "test project"},
        )
        for index, message in enumerate((
            *worker_initial,
        ), start=1):
            store.append_conversation_message("worker", f"test-initial:{index}", message)
            store.append_evidence("worker/host_logs/messages.jsonl", f"test-initial:{index}", {"kind": "initial_prompt", **message})
        reviewer_initial = (
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {"role": "user", "content": REVIEWER_INITIAL_PROMPT},
        ) if os.environ["DURABLE_TEST_SCENARIO"] == "behavior_equivalence" else (
            {"role": "system", "content": "test reviewer system"},
            {"role": "user", "content": "test reviewer initial"},
        )
        if reviewer_enabled:
            for index, message in enumerate(reviewer_initial, start=1):
                store.append_conversation_message("reviewer", f"test-initial:{index}", message)
                store.append_evidence("reviewer/host_logs/messages.jsonl", f"test-initial:{index}", {"kind": "initial_message", **message})
    initial_cursor = store.conversation_count("worker")

    # Keep test sleeps durable while making the integration cases complete quickly.
    if os.environ.get("DURABLE_TEST_SCALE_SLEEP") == "1":
        real_sleep = DBOS.sleep
        DBOS.sleep = staticmethod(lambda seconds: real_sleep(max(0.001, float(seconds) * 0.001)))

    process_id = f"{os.getpid()}:{uuid.uuid4()}"
    store.record_process_start(process_id)
    DBOS(config={
        "name": "ugs_synth_durable_process_tests",
        "application_version": "0.3.0-development-test",
        "system_database_url": "sqlite:///" + (runtime / "dbos.sqlite").resolve().as_posix(),
    })
    DBOS.launch()
    workflow_id = f"{run_id}:worker"
    status = DBOS.get_workflow_status(workflow_id)
    if status is None:
        parent_unresolved_request = None
        if os.environ["DURABLE_TEST_SCENARIO"] == "parent_unresolved_duplicate":
            parent_unresolved_request = {
                "parent_run_id": "synthetic-parent",
                "parent_request_index": 160,
                "parent_turn": 100,
                "parent_request_sha256": _request_hash(
                    worker_provider,
                    store.conversation_messages("worker"),
                    worker_tool_definitions(),
                ),
                "error_type": "RemoteDisconnected",
                "http_status": None,
            }
        with SetWorkflowID(workflow_id):
            handle = DBOS.start_workflow(
                _worker_workflow,
                run_id,
                initial_cursor,
                0,
                0,
                0,
                0,
                parent_unresolved_request,
            )
    else:
        handle = DBOS.retrieve_workflow(workflow_id)
    try:
        result = handle.get_result(polling_interval_sec=0.1)
    finally:
        DBOS.destroy()

    with sqlite3.connect(fake_state) as connection:
        provider_counts = {row[0]: row[1] for row in connection.execute("SELECT actor,SUM(count) FROM provider_requests GROUP BY actor")}
        tool_counts = {row[0]: row[1] for row in connection.execute("SELECT name,count FROM tool_dispatches")}
    provider_rows = _request_rows(fake_state)
    first_worker_request = next((row for row in provider_rows if row["actor"] == "worker"), None)
    first_worker_payload = json.loads(first_worker_request["request_body"]) if first_worker_request else {}
    tool_rows = store.tool_rows()
    summary = {
        "termination_reason": result["termination_reason"],
        "worker_responses": result["global_worker_responses"],
        "reviewer_responses": result["reviewer_global_responses"],
        "review_count": result["review_count"],
        "provider_request_counts": provider_counts,
        "worker_initial_messages": first_worker_payload.get("messages", [])[:2],
        "worker_tool_names": [
            row.get("function", {}).get("name")
            for row in first_worker_payload.get("tools", [])
            if isinstance(row, dict) and isinstance(row.get("function"), dict)
        ],
        "tool_dispatch_counts": tool_counts,
        "tool_states": {f"{row['actor']}:{row['tool_call_id']}": row["state"] for row in tool_rows},
        "worker_transcript_message_count": store.conversation_count("worker"),
        "reviewer_transcript_message_count": store.conversation_count("reviewer"),
        "suspensions": store.event_count("EXTERNAL_DEPENDENCY_SUSPENDED"),
        "resumes": store.event_count("TRAJECTORY_RESUMED"),
        "review_completed_events": store.event_count("REVIEW_COMPLETED"),
        "process_start_count": store.process_start_count(),
        "provider_attempt_states": {
            actor: [row["state"] for row in store.provider_attempt_rows(actor)]
            for actor in ("worker", "reviewer")
        },
        "provider_attempts": {
            actor: [
                {key: row[key] for key in (
                    "request_id", "attempt_index", "logical_attempt", "request_hash", "state",
                    "possible_duplicate_provider_execution",
                )}
                for row in store.provider_attempt_rows(actor)
            ]
            for actor in ("worker", "reviewer")
        },
        "worker_assistant_messages": [
            message for message in store.conversation_messages("worker")
            if message.get("role") == "assistant"
        ],
        "reviewer_assistant_messages": [
            message for message in store.conversation_messages("reviewer")
            if message.get("role") == "assistant"
        ],
        "worker_request_prepared_events": store.event_count("WORKER_REQUEST_PREPARED"),
        "worker_project_files": _workspace_files(project),
        "reviewer_project_files": _workspace_files(review),
        "reviewer_sandbox_present": reviewer_sandbox is not None,
        "reviewer_directory_present": (root / "reviewer").exists(),
    }
    if os.environ["DURABLE_TEST_SCENARIO"] == "behavior_equivalence":
        summary.update({
            "provider_requests": _request_rows(fake_state),
            "worker_transcript": store.conversation_messages("worker"),
            "reviewer_transcript": store.conversation_messages("reviewer"),
            "worker_tool_results": [
                row for row in store.evidence("worker/host_logs/messages.jsonl")
                if row.get("kind") == "tool_result"
            ],
            "reviewer_tool_results": [
                row for row in store.evidence("reviewer/host_logs/messages.jsonl")
                if row.get("kind") == "tool_result"
            ],
            "worker_workspace": _workspace_files(project),
            "reviewer_workspace": _reviewer_workspace_files(review),
            "formal_review": json.loads((root / "reviewer" / "reviews" / "review_0001" / "formal_review.json").read_text(encoding="utf-8")),
        })
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
