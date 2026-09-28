"""Durable evidence and side-effect ledger for the DBOS apparatus."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def ordered_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


class DurableStore:
    """SQLite event outbox and tool ledger; DBOS remains trajectory-state authority."""

    def __init__(self, runtime_root: Path, *, run_id: str) -> None:
        self.runtime_root = runtime_root.resolve()
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.path = self.runtime_root / "recovery_ledger.sqlite"
        self.run_id = run_id
        self.events_path = self.runtime_root / "events.jsonl"
        self._projected: dict[tuple[str, str], set[str]] = {}
        self._initialize()
        self.sync_projections()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            yield connection
        finally:
            connection.close()

    def checkpoint(self) -> None:
        """Checkpoint the WAL so the closed ledger has a stable main-file snapshot."""
        with self._connect() as connection:
            row = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if row is not None and int(row[0]) != 0:
            raise RuntimeError("recovery_ledger_checkpoint_busy")

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_index INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence_rows (
                    row_index INTEGER PRIMARY KEY AUTOINCREMENT,
                    sink TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    UNIQUE(sink, event_id)
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    actor TEXT NOT NULL,
                    message_index INTEGER NOT NULL,
                    message_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    PRIMARY KEY(actor, message_index),
                    UNIQUE(actor, message_id)
                );
                CREATE TABLE IF NOT EXISTS tool_calls (
                    actor TEXT NOT NULL,
                    tool_call_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_hash TEXT NOT NULL,
                    safe_arguments TEXT NOT NULL,
                    state TEXT NOT NULL,
                    result TEXT,
                    result_hash TEXT,
                    before_manifest TEXT,
                    after_manifest TEXT,
                    error TEXT,
                    source TEXT NOT NULL DEFAULT 'runtime',
                    PRIMARY KEY(actor, tool_call_id)
                );
                CREATE TABLE IF NOT EXISTS provider_attempts (
                    actor TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    attempt_index INTEGER NOT NULL,
                    logical_attempt INTEGER NOT NULL,
                    request_hash TEXT NOT NULL,
                    state TEXT NOT NULL,
                    possible_duplicate_provider_execution INTEGER NOT NULL DEFAULT 0,
                    raw_response_available INTEGER NOT NULL DEFAULT 0,
                    outcome TEXT,
                    PRIMARY KEY(actor, request_id, attempt_index)
                );
                CREATE INDEX IF NOT EXISTS provider_attempts_request
                    ON provider_attempts(actor, request_id, logical_attempt);
                CREATE TABLE IF NOT EXISTS counters (
                    name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS process_sessions (
                    process_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS boundary_state (
                    actor TEXT PRIMARY KEY,
                    last_request_index INTEGER NOT NULL DEFAULT 0,
                    last_response_index INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        event_id: str,
        event_type: str,
        *,
        trajectory_id: str,
        actor: str,
        global_worker_response: int | None = None,
        global_reviewer_response: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = connection.execute("SELECT payload FROM events WHERE event_id=?", (event_id,)).fetchone()
        if existing is not None:
            return json.loads(existing["payload"])
        connection.execute("INSERT INTO events(event_id,payload) VALUES(?, '{}')", (event_id,))
        event_index = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        record = {
            "event_index": event_index,
            "timestamp": utc_now(),
            "run_id": self.run_id,
            "trajectory_id": trajectory_id,
            "actor": actor,
            "event": event_type,
            "global_worker_response": global_worker_response,
            "global_reviewer_response": global_reviewer_response,
            **(payload or {}),
        }
        serialized = json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False)
        connection.execute("UPDATE events SET payload=? WHERE event_index=?", (serialized, event_index))
        return record

    def emit_event(
        self,
        event_id: str,
        event_type: str,
        *,
        trajectory_id: str,
        actor: str,
        global_worker_response: int | None = None,
        global_reviewer_response: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT payload FROM events WHERE event_id=?", (event_id,)).fetchone()
            record = self._insert_event(
                connection,
                event_id,
                event_type,
                trajectory_id=trajectory_id,
                actor=actor,
                global_worker_response=global_worker_response,
                global_reviewer_response=global_reviewer_response,
                payload=payload,
            )
            connection.commit()
        if existing is None:
            self._append_projection(self.events_path, record, key="event_index")
        return record

    def append_evidence(self, sink: str, event_id: str, record: dict[str, Any]) -> dict[str, Any]:
        if Path(sink).is_absolute() or ".." in Path(sink).parts:
            raise ValueError("evidence sink must stay inside the run root")
        output = {"timestamp": utc_now(), **record, "durable_event_id": event_id}
        serialized = json.dumps(output, ensure_ascii=False, sort_keys=True, allow_nan=False)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM evidence_rows WHERE sink=? AND event_id=?", (sink, event_id)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO evidence_rows(sink,event_id,payload) VALUES(?,?,?)",
                    (sink, event_id, serialized),
                )
                output = json.loads(serialized)
                is_new = True
            else:
                output = json.loads(row["payload"])
                is_new = False
            connection.commit()
        if is_new:
            self._append_projection(self.runtime_root.parent / sink, output, key="durable_event_id")
        return output

    def _append_projection(self, path: Path, record: dict[str, Any], *, key: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        value = record.get(key)
        identity = (str(path.resolve()), key)
        projected = self._projected.get(identity)
        if projected is None:
            projected = set()
            if path.is_file():
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            existing = json.loads(line).get(key)
                            if existing is not None:
                                projected.add(str(existing))
                        except json.JSONDecodeError:
                            continue
            self._projected[identity] = projected
        if str(value) in projected:
            return
        line = (json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o666)
        try:
            os.write(descriptor, line)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        projected.add(str(value))

    def sync_projections(self) -> None:
        with self._connect() as connection:
            events = [json.loads(row["payload"]) for row in connection.execute("SELECT payload FROM events ORDER BY event_index")]
            evidence = [dict(row) for row in connection.execute("SELECT sink,event_id,payload FROM evidence_rows ORDER BY row_index")]
        for event in events:
            self._append_projection(self.events_path, event, key="event_index")
        for row in evidence:
            payload = json.loads(row["payload"])
            self._append_projection(self.runtime_root.parent / row["sink"], payload, key="durable_event_id")

    def event_count(self, event_type: str | None = None) -> int:
        with self._connect() as connection:
            if event_type is None:
                return int(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
            count = 0
            for row in connection.execute("SELECT payload FROM events"):
                if json.loads(row["payload"]).get("event") == event_type:
                    count += 1
            return count

    def event_rows(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM events ORDER BY event_index").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def evidence(self, sink: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM evidence_rows WHERE sink=? ORDER BY row_index", (sink,)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def evidence_count(self, sink: str, *, kind: str | None = None) -> int:
        rows = self.evidence(sink)
        return sum(1 for row in rows if kind is None or row.get("kind") == kind)

    def append_conversation_message(
        self, actor: str, message_id: str, message: dict[str, Any]
    ) -> int:
        payload = ordered_json(message)
        payload_hash = sha256_bytes(payload.encode("utf-8"))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT message_index,payload_hash FROM conversation_messages WHERE actor=? AND message_id=?",
                (actor, message_id),
            ).fetchone()
            if existing is not None:
                if existing["payload_hash"] != payload_hash:
                    connection.rollback()
                    raise RuntimeError("conversation_message_id_reused_with_different_payload")
                index = int(existing["message_index"])
                connection.commit()
                return index
            row = connection.execute(
                "SELECT COALESCE(MAX(message_index),0)+1 AS next_index FROM conversation_messages WHERE actor=?",
                (actor,),
            ).fetchone()
            index = int(row["next_index"])
            connection.execute(
                "INSERT INTO conversation_messages(actor,message_index,message_id,payload,payload_hash) VALUES(?,?,?,?,?)",
                (actor, index, message_id, payload, payload_hash),
            )
            connection.commit()
        return index

    def conversation_count(self, actor: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(message_index),0) FROM conversation_messages WHERE actor=?", (actor,)
            ).fetchone()
        return int(row[0])

    def conversation_messages(self, actor: str, *, through_index: int | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if through_index is None:
                rows = connection.execute(
                    "SELECT payload FROM conversation_messages WHERE actor=? ORDER BY message_index", (actor,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT payload FROM conversation_messages WHERE actor=? AND message_index<=? ORDER BY message_index",
                    (actor, through_index),
                ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def conversation_message(self, actor: str, message_index: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM conversation_messages WHERE actor=? AND message_index=?",
                (actor, message_index),
            ).fetchone()
        return json.loads(row["payload"]) if row is not None else None

    def set_counter_at_least(self, name: str, value: int) -> int:
        if value < 0:
            raise ValueError("counter value must be non-negative")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO counters(name,value) VALUES(?,?) "
                "ON CONFLICT(name) DO UPDATE SET value=MAX(value,excluded.value)",
                (name, value),
            )
            result = int(connection.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()[0])
            connection.commit()
        return result

    def counter(self, name: str) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()
        return int(row[0]) if row is not None else 0

    def increment_counter(self, name: str, *, amount: int = 1) -> int:
        if amount < 0:
            raise ValueError("counter increment must be non-negative")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO counters(name,value) VALUES(?,?) "
                "ON CONFLICT(name) DO UPDATE SET value=value+excluded.value",
                (name, amount),
            )
            result = int(connection.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()[0])
            connection.commit()
        return result

    def provider_attempt_rows(self, actor: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM provider_attempts WHERE actor=? ORDER BY attempt_index", (actor,)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["outcome"] = json.loads(item["outcome"]) if item["outcome"] else None
            item["possible_duplicate_provider_execution"] = bool(item["possible_duplicate_provider_execution"])
            item["raw_response_available"] = bool(item["raw_response_available"])
            result.append(item)
        return result

    def import_provider_attempt(
        self,
        *,
        actor: str,
        request_id: str,
        attempt_index: int,
        logical_attempt: int,
        request_hash: str,
        state: str,
        outcome: dict[str, Any] | None,
        possible_duplicate: bool = False,
        raw_response_available: bool = False,
    ) -> None:
        if state not in {"SUCCEEDED", "FAILED", "PREPARED", "SENT", "RESPONSE_REDACTED"}:
            raise ValueError("invalid imported provider-attempt state")
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO provider_attempts "
                "(actor,request_id,attempt_index,logical_attempt,request_hash,state,possible_duplicate_provider_execution,raw_response_available,outcome) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    actor,
                    request_id,
                    attempt_index,
                    logical_attempt,
                    request_hash,
                    state,
                    int(possible_duplicate),
                    int(raw_response_available),
                    canonical_json(outcome) if outcome is not None else None,
                ),
            )

    def seed_boundary_state(self, actor: str, *, last_request_index: int, last_response_index: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO boundary_state(actor,last_request_index,last_response_index) VALUES(?,?,?) "
                "ON CONFLICT(actor) DO UPDATE SET "
                "last_request_index=MAX(last_request_index,excluded.last_request_index), "
                "last_response_index=MAX(last_response_index,excluded.last_response_index)",
                (actor, last_request_index, last_response_index),
            )

    def record_process_start(self, process_id: str) -> int:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO process_sessions(process_id,started_at) VALUES(?,?)",
                (process_id, utc_now()),
            )
            count = int(connection.execute("SELECT COUNT(*) FROM process_sessions").fetchone()[0])
            connection.commit()
        return count

    def process_start_count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM process_sessions").fetchone()[0])

    def reserve_boundary_request_index(self, actor: str) -> int:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT COALESCE(MAX(last_request_index),0) AS current FROM boundary_state").fetchone()
            next_index = int(row["current"]) + 1
            connection.execute(
                "INSERT INTO boundary_state(actor,last_request_index,last_response_index) VALUES(?,?,0) "
                "ON CONFLICT(actor) DO UPDATE SET last_request_index=excluded.last_request_index",
                (actor, next_index),
            )
            connection.commit()
        return next_index

    def note_boundary_response(self, actor: str, request_index: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO boundary_state(actor,last_request_index,last_response_index) VALUES(?,?,?) "
                "ON CONFLICT(actor) DO UPDATE SET last_response_index=MAX(last_response_index,excluded.last_response_index)",
                (actor, request_index, request_index),
            )

    def boundary_state(self, actor: str) -> tuple[int | None, int | None]:
        with self._connect() as connection:
            row = connection.execute("SELECT last_request_index,last_response_index FROM boundary_state WHERE actor=?", (actor,)).fetchone()
        if row is None:
            return None, None
        return int(row["last_request_index"]) or None, int(row["last_response_index"]) or None

    def prepare_tool(
        self,
        *,
        actor: str,
        tool_call_id: str,
        tool_name: str,
        safe_arguments: dict[str, Any],
        before_manifest: dict[str, Any] | None,
        trajectory_id: str,
        global_worker_response: int | None,
        global_reviewer_response: int | None,
    ) -> dict[str, Any]:
        args_json = canonical_json(safe_arguments)
        args_hash = sha256_bytes(args_json.encode("utf-8"))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM tool_calls WHERE actor=? AND tool_call_id=?", (actor, tool_call_id)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO tool_calls(actor,tool_call_id,tool_name,arguments_hash,safe_arguments,state,before_manifest) "
                    "VALUES(?,?,?,?,?,'PREPARED',?)",
                    (actor, tool_call_id, tool_name, args_hash, args_json,
                     canonical_json(before_manifest) if before_manifest is not None else None),
                )
                row = connection.execute(
                    "SELECT * FROM tool_calls WHERE actor=? AND tool_call_id=?", (actor, tool_call_id)
                ).fetchone()
            elif row["tool_name"] != tool_name or row["arguments_hash"] != args_hash:
                connection.rollback()
                raise RuntimeError("tool_call_id_reused_with_different_arguments")
            state = dict(row)
            event = self._insert_event(
                connection,
                f"tool:{actor}:{tool_call_id}:prepared",
                "TOOL_CALL_PREPARED",
                trajectory_id=trajectory_id,
                actor=actor,
                global_worker_response=global_worker_response,
                global_reviewer_response=global_reviewer_response,
                payload={
                    "tool_call_id": tool_call_id,
                    "tool": tool_name,
                    "arguments_hash": args_hash,
                    "safe_arguments": safe_arguments,
                    "workspace_before_sha256": sha256_json(before_manifest) if before_manifest is not None else None,
                },
            )
            connection.commit()
        self._append_projection(self.events_path, event, key="event_index")
        return state

    def mark_tool_executing(self, actor: str, tool_call_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM tool_calls WHERE actor=? AND tool_call_id=?", (actor, tool_call_id)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise RuntimeError("tool_call_not_prepared")
            state = dict(row)
            if state["state"] == "PREPARED":
                connection.execute(
                    "UPDATE tool_calls SET state='EXECUTING' WHERE actor=? AND tool_call_id=?",
                    (actor, tool_call_id),
                )
                state["state"] = "EXECUTING"
            connection.commit()
        return state

    def record_tool_observed(
        self,
        actor: str,
        tool_call_id: str,
        *,
        result: dict[str, Any],
        after_manifest: dict[str, Any] | None,
    ) -> dict[str, Any]:
        result_json = canonical_json(result)
        result_hash = sha256_bytes(result_json.encode("utf-8"))
        after_json = canonical_json(after_manifest) if after_manifest is not None else None
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM tool_calls WHERE actor=? AND tool_call_id=?", (actor, tool_call_id)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise RuntimeError("tool_call_not_prepared")
            if row["state"] == "COMMITTED":
                connection.commit()
                return dict(row)
            connection.execute(
                "UPDATE tool_calls SET state='SIDE_EFFECTS_OBSERVED',result=?,result_hash=?,after_manifest=? "
                "WHERE actor=? AND tool_call_id=?",
                (result_json, result_hash, after_json, actor, tool_call_id),
            )
            connection.commit()
        return self.get_tool(actor, tool_call_id) or {}

    def commit_tool(
        self,
        actor: str,
        tool_call_id: str,
        *,
        trajectory_id: str,
        global_worker_response: int | None,
        global_reviewer_response: int | None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM tool_calls WHERE actor=? AND tool_call_id=?", (actor, tool_call_id)
            ).fetchone()
            if row is None or row["result"] is None:
                connection.rollback()
                raise RuntimeError("tool_call_result_not_observed")
            if row["state"] != "COMMITTED":
                connection.execute(
                    "UPDATE tool_calls SET state='COMMITTED' WHERE actor=? AND tool_call_id=?",
                    (actor, tool_call_id),
                )
            state = dict(connection.execute(
                "SELECT * FROM tool_calls WHERE actor=? AND tool_call_id=?", (actor, tool_call_id)
            ).fetchone())
            after = json.loads(state["after_manifest"]) if state["after_manifest"] else None
            before = json.loads(state["before_manifest"]) if state["before_manifest"] else None
            event = self._insert_event(
                connection,
                f"tool:{actor}:{tool_call_id}:committed",
                "TOOL_CALL_COMMITTED",
                trajectory_id=trajectory_id,
                actor=actor,
                global_worker_response=global_worker_response,
                global_reviewer_response=global_reviewer_response,
                payload={
                    "tool_call_id": tool_call_id,
                    "tool": state["tool_name"],
                    "result_hash": state["result_hash"],
                    "workspace_before_sha256": sha256_json(before) if before is not None else None,
                    "workspace_after_sha256": sha256_json(after) if after is not None else None,
                },
            )
            connection.commit()
        self._append_projection(self.events_path, event, key="event_index")
        state["result"] = json.loads(state["result"])
        state["before_manifest"] = before
        state["after_manifest"] = after
        return state

    def mark_tool_uncertain(self, actor: str, tool_call_id: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE tool_calls SET state='TOOL_EXECUTION_STATE_UNCERTAIN',error=? WHERE actor=? AND tool_call_id=?",
                (error, actor, tool_call_id),
            )

    def get_tool(self, actor: str, tool_call_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tool_calls WHERE actor=? AND tool_call_id=?", (actor, tool_call_id)
            ).fetchone()
        return dict(row) if row is not None else None

    def tool_rows(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM tool_calls ORDER BY actor,tool_call_id").fetchall()
        return [dict(row) for row in rows]

    def import_committed_tool(
        self,
        *,
        actor: str,
        tool_call_id: str,
        tool_name: str,
        safe_arguments: dict[str, Any],
        result: dict[str, Any],
        source: str,
    ) -> None:
        args_json = canonical_json(safe_arguments)
        result_json = canonical_json(result)
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO tool_calls(actor,tool_call_id,tool_name,arguments_hash,safe_arguments,state,result,result_hash,source) "
                "VALUES(?,?,?,?,?,'COMMITTED',?,?,?)",
                (actor, tool_call_id, tool_name, sha256_bytes(args_json.encode("utf-8")), args_json,
                 result_json, sha256_bytes(result_json.encode("utf-8")), source),
            )

    def prepare_provider_attempt(
        self,
        *,
        actor: str,
        request_id: str,
        logical_attempt: int,
        request_hash: str,
    ) -> int:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT attempt_index FROM provider_attempts WHERE actor=? AND request_id=? AND logical_attempt=? "
                "ORDER BY attempt_index LIMIT 1",
                (actor, request_id, logical_attempt),
            ).fetchone()
            if row is not None:
                attempt_index = int(row["attempt_index"])
                connection.commit()
                return attempt_index
            maximum = connection.execute("SELECT COALESCE(MAX(attempt_index),0) AS n FROM provider_attempts WHERE actor=?", (actor,)).fetchone()
            attempt_index = int(maximum["n"]) + 1
            connection.execute(
                "INSERT INTO provider_attempts(actor,request_id,attempt_index,logical_attempt,request_hash,state) "
                "VALUES(?,?,?,?,?,'PREPARED')",
                (actor, request_id, attempt_index, logical_attempt, request_hash),
            )
            connection.commit()
        return attempt_index

    def begin_provider_call(self, actor: str, request_id: str, planned_index: int) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM provider_attempts WHERE actor=? AND request_id=? AND attempt_index=?",
                (actor, request_id, planned_index),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise RuntimeError("provider_attempt_not_prepared")
            state = dict(row)
            if state["state"] in {"SUCCEEDED", "FAILED", "RESPONSE_REDACTED"}:
                connection.commit()
                state["outcome"] = json.loads(state["outcome"]) if state["outcome"] else None
                return state
            if state["state"] == "PREPARED":
                state["possible_duplicate_provider_execution"] = 0
                connection.commit()
                return state
            latest = connection.execute(
                "SELECT * FROM provider_attempts WHERE actor=? AND request_id=? AND logical_attempt=? "
                "ORDER BY attempt_index DESC LIMIT 1",
                (actor, request_id, int(state["logical_attempt"])),
            ).fetchone()
            if latest is not None and latest["state"] in {"SUCCEEDED", "FAILED"}:
                connection.commit()
                recovered = dict(latest)
                recovered["outcome"] = json.loads(recovered["outcome"]) if recovered["outcome"] else None
                return recovered
            maximum = connection.execute(
                "SELECT COALESCE(MAX(attempt_index),0) AS n FROM provider_attempts WHERE actor=?", (actor,)
            ).fetchone()
            duplicate_index = int(maximum["n"]) + 1
            connection.execute(
                "INSERT INTO provider_attempts(actor,request_id,attempt_index,logical_attempt,request_hash,state,possible_duplicate_provider_execution) "
                "VALUES(?,?,?,?,?,'PREPARED',1)",
                (actor, request_id, duplicate_index, int(state["logical_attempt"]), state["request_hash"]),
            )
            duplicate = dict(connection.execute(
                "SELECT * FROM provider_attempts WHERE actor=? AND request_id=? AND attempt_index=?",
                (actor, request_id, duplicate_index),
            ).fetchone())
            connection.commit()
            duplicate["possible_duplicate_provider_execution"] = True
            return duplicate

    def note_provider_request_sent(self, actor: str, request_id: str, attempt_index: int) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE provider_attempts SET state='SENT' WHERE actor=? AND request_id=? AND attempt_index=? AND state='PREPARED'",
                (actor, request_id, attempt_index),
            )

    def record_provider_outcome(
        self,
        actor: str,
        request_id: str,
        attempt_index: int,
        *,
        state: str,
        outcome: dict[str, Any],
        raw_response_available: bool,
        possible_duplicate: bool,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE provider_attempts SET state=?,outcome=?,raw_response_available=?,possible_duplicate_provider_execution=? "
                "WHERE actor=? AND request_id=? AND attempt_index=?",
                (state, ordered_json(outcome), int(raw_response_available), int(possible_duplicate), actor, request_id, attempt_index),
            )

    def provider_attempt(self, actor: str, request_id: str, attempt_index: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM provider_attempts WHERE actor=? AND request_id=? AND attempt_index=?",
                (actor, request_id, attempt_index),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["outcome"] = json.loads(result["outcome"]) if result["outcome"] else None
        result["possible_duplicate_provider_execution"] = bool(result["possible_duplicate_provider_execution"])
        result["raw_response_available"] = bool(result["raw_response_available"])
        return result

    def save_provider_response_from_boundary(
        self,
        *,
        actor: str,
        request_id: str,
        attempt_index: int,
        outcome: dict[str, Any],
        redacted: bool,
        possible_duplicate: bool = False,
    ) -> None:
        if redacted:
            self.record_provider_outcome(
                actor, request_id, attempt_index, state="RESPONSE_REDACTED",
                outcome={"status": "response_redacted"}, raw_response_available=True,
                possible_duplicate=possible_duplicate,
            )
            return
        self.record_provider_outcome(
            actor, request_id, attempt_index, state="SUCCEEDED", outcome=outcome,
            raw_response_available=True, possible_duplicate=possible_duplicate,
        )

    def provider_attempt_count(self, actor: str) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM provider_attempts WHERE actor=?", (actor,)).fetchone()[0])
