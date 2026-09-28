from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review import durable_replication
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.durable_store import DurableStore
from self_organizing_engineering_agent.experiments.pilot_1a.isolation import AgentSandbox


def test_worker_only_fresh_setup_never_creates_or_deletes_a_reviewer_sandbox(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    env_file = repo_root / ".env"
    env_file.touch()
    public_root = repo_root / "public"
    public_root.mkdir()
    sandbox_calls: list[bool] = []

    class FakeProvider:
        credential_configured = False

    monkeypatch.setattr(durable_replication, "_public_world", lambda _: (public_root, {"brief.json": "sha256"}))
    monkeypatch.setattr(durable_replication, "_provider_env_file", lambda *_: env_file)
    monkeypatch.setattr(durable_replication, "DeepSeekProvider", lambda **_: FakeProvider())
    monkeypatch.setattr(durable_replication, "inspect_image", lambda _: {"available": True, "image_id": "test-image"})

    def make_sandbox(root: Path, *, reviewer: bool, public_root: Path) -> AgentSandbox:
        sandbox_calls.append(reviewer)
        actor = root / ("reviewer" if reviewer else "worker") / "sandbox"
        view = actor / "agent_view"
        brief = view / "brief"
        project = view / ("review" if reviewer else "project")
        brief.mkdir(parents=True)
        project.mkdir(parents=True)
        return AgentSandbox(actor.resolve(), view.resolve(), brief.resolve(), project.resolve())

    monkeypatch.setattr(durable_replication, "_sandbox", make_sandbox)
    monkeypatch.setattr(durable_replication, "DockerExecutor", lambda **_: object())
    monkeypatch.setattr(durable_replication, "_probe_worker_runtime", lambda _: {"passed": True})
    monkeypatch.setattr(
        durable_replication,
        "_probe_reviewer_runtime",
        lambda *_: (_ for _ in ()).throw(AssertionError("Reviewer probe must not run in Worker-only")),
    )
    monkeypatch.setattr(durable_replication, "_workspace_manifest", lambda _: {"file_count": 0, "files": {}})
    monkeypatch.setattr(durable_replication, "_environment_record", lambda *_: {"provider_environment_file_present": True})
    monkeypatch.setattr(
        durable_replication,
        "_provider_record",
        lambda *_args, **_kwargs: {"configured_model": "deepseek-flash", "effective_model": "deepseek-flash"},
    )
    monkeypatch.setattr(durable_replication, "_source_hashes", lambda _: {})
    monkeypatch.setattr(durable_replication, "_git_head", lambda _: "test-head")
    monkeypatch.setattr(durable_replication, "MinimalUGSSynthTools", lambda *_: object())

    run_root, context, _worker, reviewer = durable_replication._prepare_fresh_run(
        repo_root,
        runs_root=tmp_path / "runs",
        run_id="worker-only-portability-test",
        condition="worker_only",
        env_file=env_file,
        image="test-image",
    )
    freeze = json.loads((run_root / "freeze.json").read_text(encoding="utf-8"))

    assert sandbox_calls == [False]
    assert reviewer is None
    assert context.reviewer_sandbox is None
    assert context.reviewer_provider is None
    assert not (run_root / "reviewer").exists()
    assert freeze["reviewer_provider"] is None
    assert freeze["capabilities"]["reviewer_available"] is False
    assert freeze["pre_run_checks"]["worker_only_baseline_tool_surface"] is True


def test_cost_estimate_uses_official_peak_and_off_peak_rates_per_response() -> None:
    rows = [
        {
            "timestamp": "2026-09-24T02:00:00Z",
            "usage": {
                "prompt_tokens": 10,
                "prompt_cache_hit_tokens": 2,
                "prompt_cache_miss_tokens": 8,
                "completion_tokens": 3,
            },
        },
        {
            "timestamp": "2026-09-24T15:00:00Z",
            "usage": {
                "prompt_tokens": 10,
                "prompt_cache_hit_tokens": 5,
                "prompt_cache_miss_tokens": 5,
                "completion_tokens": 2,
            },
        },
    ]

    totals, estimate = durable_replication._usage_and_cost(rows)

    assert totals["prompt_tokens"] == 20
    assert totals["completion_tokens"] == 5
    assert estimate["estimated_cost_usd"] == 0.00003
    assert estimate["priced_response_count"] == 2
    assert estimate["peak_priced_response_count"] == 1
    assert estimate["estimate_only_not_provider_invoice"] is True
    assert estimate["possible_duplicate_provider_execution_cost_not_included"] is True


def test_error_recovery_selects_the_failed_dbos_function_checkpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        durable_replication.DBOS,
        "get_workflow_status",
        lambda workflow_id: SimpleNamespace(status="ERROR"),
    )
    monkeypatch.setattr(
        durable_replication.DBOS,
        "list_workflow_steps",
        lambda workflow_id: [
            {"function_id": 11, "function_name": "durable_provider_call", "error": None},
            {"function_id": 26, "function_name": "durable_prepare_tool_call", "error": "step failed"},
        ],
    )

    assert durable_replication._failed_workflow_step("replication:reviewer:0001") == (26, "durable_prepare_tool_call")


def test_final_checkpoint_closes_sqlite_connection_before_hashing(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "dbos.sqlite"
    real_connection = sqlite3.connect(database)

    class TrackedConnection:
        closed = False

        def execute(self, *args, **kwargs):
            return real_connection.execute(*args, **kwargs)

        def close(self) -> None:
            self.closed = True
            real_connection.close()

    tracked = TrackedConnection()
    monkeypatch.setattr(durable_replication.sqlite3, "connect", lambda *_args, **_kwargs: tracked)

    durable_replication._checkpoint_and_close_sqlite(database)

    assert tracked.closed is True


def test_artifact_hashes_preserve_sqlite_sidecars_when_present(tmp_path: Path) -> None:
    (tmp_path / "runtime").mkdir()
    for filename in (
        "dbos.sqlite",
        "dbos.sqlite-wal",
        "dbos.sqlite-shm",
        "dbos.sqlite-journal",
    ):
        (tmp_path / "runtime" / filename).write_bytes(filename.encode("ascii"))

    hashes = durable_replication._artifact_hashes(tmp_path)

    assert set(hashes) == {
        "runtime/dbos.sqlite",
        "runtime/dbos.sqlite-wal",
        "runtime/dbos.sqlite-shm",
        "runtime/dbos.sqlite-journal",
    }


def test_durable_store_context_closes_every_sqlite_connection(tmp_path: Path, monkeypatch) -> None:
    real_connect = sqlite3.connect
    connections: list[sqlite3.Connection] = []
    closed_ids: set[int] = set()

    class TrackedConnection(sqlite3.Connection):
        def close(self) -> None:
            closed_ids.add(id(self))
            super().close()

    def tracked_connect(*args, **kwargs):
        kwargs["factory"] = TrackedConnection
        connection = real_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(durable_replication.sqlite3, "connect", tracked_connect)
    store = DurableStore(tmp_path / "runtime", run_id="connection-close-test")
    store.append_evidence("worker/host_logs/messages.jsonl", "row-1", {"kind": "test"})
    store.checkpoint()

    assert connections
    assert all(id(connection) in closed_ids for connection in connections)
    assert not (tmp_path / "runtime" / "recovery_ledger.sqlite-wal").exists()
    assert not (tmp_path / "runtime" / "recovery_ledger.sqlite-shm").exists()
