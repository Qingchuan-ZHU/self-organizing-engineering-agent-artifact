from __future__ import annotations

import hashlib
import json
from email.message import Message
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from typing import Any

import pytest

from self_organizing_engineering_agent.experiments.pilot_1a.deepseek_provider import DeepSeekProvider
from self_organizing_engineering_agent.experiments.pilot_1a.provider import ProviderCallError
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review import runner
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.provider_boundary import (
    ProviderBoundaryLogger,
    sanitize_headers,
)
from self_organizing_engineering_agent.experiments.ugs_synth_interleaved_review.tools import worker_tool_definitions


class FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self._body = body
        self._status = status
        self.headers = Message()
        for key, value in (headers or {"Content-Type": "application/json"}).items():
            self.headers[key] = value

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def getcode(self) -> int:
        return self._status

    def read(self) -> bytes:
        return self._body


class ResponseQueue:
    def __init__(self, payloads: list[dict[str, Any] | BaseException]) -> None:
        self.payloads = list(payloads)
        self.sent_bodies: list[bytes] = []
        self.calls = 0

    def __call__(self, request, *, timeout):  # type: ignore[no-untyped-def]
        del timeout
        self.calls += 1
        self.sent_bodies.append(request.data)
        next_response = self.payloads.pop(0)
        if isinstance(next_response, BaseException):
            raise next_response
        return FakeResponse(json.dumps(next_response, ensure_ascii=False).encode("utf-8"))


def completion(
    message: dict[str, Any],
    *,
    finish_reason: str = "stop",
    response_id: str = "response-1",
) -> dict[str, Any]:
    return {
        "id": response_id,
        "model": "deepseek-flash",
        "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
    }


def provider(queue: ResponseQueue, *, api_key: str = "unit-test-key", base_url: str = "https://unit.test/v1") -> DeepSeekProvider:
    return DeepSeekProvider(api_key=api_key, base_url=base_url, urlopen_fn=queue)


def event_rows(run_root: Path) -> list[dict[str, Any]]:
    path = run_root / "provider_logs" / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def configure_observability(provider_instance: DeepSeekProvider, run_root: Path, run_id: str, actor: str = "worker") -> ProviderBoundaryLogger:
    logger = ProviderBoundaryLogger(run_root, run_id)
    provider_instance.enable_boundary_observability(logger, context={"run_id": run_id, "actor": actor})
    return logger


def test_request_log_captures_final_serialized_transport_body(tmp_path: Path) -> None:
    queue = ResponseQueue([completion({"role": "assistant", "content": "ok"})])
    client = provider(queue)
    configure_observability(client, tmp_path, "request-test")
    messages = [{"role": "user", "content": "hello"}]
    tools = worker_tool_definitions()

    client.generate_with_native_tools(messages, tools, max_output_tokens=321)

    request_row = next(row for row in event_rows(tmp_path) if row["event"] == "request")
    actual_bytes = queue.sent_bodies[0]
    assert request_row["serialized_body"] == actual_bytes.decode("utf-8")
    assert request_row["serialized_body_sha256"] == hashlib.sha256(actual_bytes).hexdigest()
    assert json.loads(request_row["serialized_body"]) == json.loads(actual_bytes)
    assert json.loads(request_row["serialized_body"])["tool_choice"] == "auto"
    assert json.loads(request_row["serialized_body"])["max_tokens"] == 321
    assert request_row["http_method"] == "POST"
    assert request_row["request_headers"] == {"accept": "application/json", "content-type": "application/json"}


def test_raw_response_parsed_object_and_runtime_message_are_separate(tmp_path: Path) -> None:
    message = {"role": "assistant", "content": "", "reasoning_content": "continue working..."}
    raw_payload = completion(message, finish_reason="stop", response_id="response-empty-stop")
    raw_body = json.dumps(raw_payload, ensure_ascii=False).encode("utf-8")
    queue = ResponseQueue([raw_payload])
    client = provider(queue)
    configure_observability(client, tmp_path, "layer-test")

    result = client.generate_with_native_tools([], worker_tool_definitions(), max_output_tokens=10)

    rows = event_rows(tmp_path)
    assert [row["event"] for row in rows] == ["request", "response_raw", "response_parsed", "runtime_assistant"]
    assert rows[1]["raw_body"] == raw_body.decode("utf-8")
    assert rows[1]["raw_body_sha256"] == hashlib.sha256(raw_body).hexdigest()
    assert rows[2]["parsed_provider_object"]["choices"][0]["message"] == message
    assert rows[3]["runtime_assistant_message"] == result.assistant_message == message
    assert rows[3]["finish_reason"] == "stop"
    assert rows[3]["content"] == ""
    assert rows[3]["reasoning_content"] == "continue working..."


class WorkerTools:
    def __init__(self, project_root: Path) -> None:
        self.sandbox = SimpleNamespace(project_root=project_root)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return {"status": "finish_requested"} if name == "finish_project" else {"files": []}


def run_worker(provider_instance: DeepSeekProvider, run_root: Path, tools: WorkerTools) -> dict[str, Any]:
    instrumentation = runner.RunInstrumentation(run_root)
    observer = getattr(provider_instance, "_boundary_observer", None)
    if isinstance(observer, ProviderBoundaryLogger):
        instrumentation.provider_boundary_logger = observer
    return runner._run_worker(provider_instance, tools, instrumentation)


def test_length_continuations_record_exact_replayed_messages(tmp_path: Path) -> None:
    first = {"role": "assistant", "content": "", "reasoning_content": "reasoning-one"}
    second = {"role": "assistant", "content": "", "reasoning_content": "reasoning-two"}
    final = {"role": "assistant", "content": "done", "reasoning_content": "finished after replay"}
    queue = ResponseQueue([
        completion(first, finish_reason="length", response_id="length-1"),
        completion(second, finish_reason="length", response_id="length-2"),
        completion(final, finish_reason="stop", response_id="stop-3"),
    ])
    client = provider(queue)
    configure_observability(client, tmp_path / "continuation-run", "continuation-run")
    tools = WorkerTools(tmp_path / "project")
    tools.sandbox.project_root.mkdir()

    result = run_worker(client, tmp_path / "continuation-run", tools)

    requests = [row for row in event_rows(tmp_path / "continuation-run") if row["event"] == "request"]
    first_continuation, second_continuation = [row["continuation"] for row in requests[1:]]
    assert result["length_continuations"] == 2
    assert result["termination_reason"] == "assistant_stopped_without_finish_project"
    assert first_continuation["continuation_index"] == 1
    assert first_continuation["triggering_response_index"] == requests[0]["request_index"]
    assert first_continuation["assistant_message_replayed"] == first
    assert first_continuation["new_request_messages"][-1] == first
    assert first_continuation["reasoning_content_preserved"] is True
    assert second_continuation["continuation_index"] == 2
    assert second_continuation["triggering_response_index"] == requests[1]["request_index"]
    assert second_continuation["assistant_message_replayed"] == second
    assert second_continuation["new_request_messages"][-1] == second


def test_tool_call_result_pairing_is_present_in_the_next_request(tmp_path: Path) -> None:
    call = {"id": "call-list-1", "type": "function", "function": {"name": "list_files", "arguments": "{}"}}
    final = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": "finish-2", "type": "function", "function": {"name": "finish_project", "arguments": "{}"}}],
    }
    queue = ResponseQueue([
        completion({"role": "assistant", "content": "", "tool_calls": [call]}, finish_reason="tool_calls", response_id="tool-1"),
        completion(final, finish_reason="tool_calls", response_id="tool-2"),
    ])
    client = provider(queue)
    run_root = tmp_path / "tool-run"
    configure_observability(client, run_root, "tool-run")
    project = tmp_path / "tool-project"
    project.mkdir()
    tools = WorkerTools(project)

    result = run_worker(client, run_root, tools)

    request_rows = [row for row in event_rows(run_root) if row["event"] == "request"]
    second_request = json.loads(request_rows[1]["serialized_body"])
    assert result["termination_reason"] == "agent_completed"
    assert tools.calls == [("list_files", {}), ("finish_project", {})]
    assert request_rows[1]["preceding_tool_call_ids"] == ["call-list-1"]
    assert request_rows[1]["preceding_tool_result_ids"] == ["call-list-1"]
    assert second_request["messages"][-2]["tool_calls"][0]["id"] == "call-list-1"
    assert second_request["messages"][-1] == {"role": "tool", "tool_call_id": "call-list-1", "content": "{\"files\": []}"}


def test_secret_headers_and_body_values_are_redacted(tmp_path: Path) -> None:
    payload = completion({"role": "assistant", "content": "Bearer API_SECRET; Authorization: Bearer UNLISTED_SECRET"})
    payload["my_api_key"] = "RESPONSE_SECRET"
    queue = ResponseQueue([payload])
    client = provider(queue, api_key="API_SECRET", base_url="https://user:pass@unit.test/v1?token=QUERY_SECRET")
    configure_observability(client, tmp_path, "redaction-test")

    client._send_payload({
        "model": "deepseek-flash",
        "api_key": "BODY_SECRET",
        "x_api_key": "NAMED_SECRET",
        "messages": [{"role": "user", "content": "Bearer API_SECRET; api-key=TEXT_SECRET; Authorization: Bearer UNLISTED_SECRET"}],
    })

    event_text = (tmp_path / "provider_logs" / "events.jsonl").read_text(encoding="utf-8")
    assert all(secret not in event_text for secret in ("API_SECRET", "BODY_SECRET", "NAMED_SECRET", "TEXT_SECRET", "QUERY_SECRET", "RESPONSE_SECRET", "COOKIE_SECRET", "UNLISTED_SECRET"))
    request_row = next(row for row in event_rows(tmp_path) if row["event"] == "request")
    assert request_row["serialized_body_redacted"] is True
    assert "<REDACTED>" in request_row["serialized_body"]
    assert "unit.test/v1/chat/completions" in request_row["endpoint_identifier"]
    assert "QUERY_SECRET" not in request_row["endpoint_identifier"]
    assert sanitize_headers({
        "Authorization": "Bearer SECRET",
        "api-key": "SECRET",
        "Cookie": "COOKIE_SECRET",
        "Content-Type": "application/json",
        "X-Request-Id": "request-1",
    }) == {"content-type": "application/json", "x-request-id": "request-1"}


def test_transport_http_and_parse_errors_are_logged_without_changing_error_contract(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    delays: list[float] = []
    monkeypatch.setattr(runner.time, "sleep", delays.append)
    transport_queue = ResponseQueue([
        URLError("Bearer API_SECRET at https://user:pass@unit.test/p?token=QUERY_SECRET")
        for _ in range(6)
    ])
    client = provider(transport_queue, api_key="API_SECRET")
    logger = configure_observability(client, tmp_path / "transport", "transport")
    instrumentation = runner.RunInstrumentation(tmp_path / "transport")
    instrumentation.provider_boundary_logger = logger
    with pytest.raises(ProviderCallError) as transport_error:
        runner._generate_with_transport_retry(
            client,
            [],
            worker_tool_definitions(),
            max_output_tokens=10,
            instrumentation=instrumentation,
            role="worker",
            turn=1,
        )
    assert transport_error.value.details == {
        "error_type": "URLError",
        "category": "provider_transport_error",
        "http_status": None,
        "requested_model": "deepseek-flash",
    }
    assert transport_queue.calls == 6
    assert delays == [2, 5, 10, 20, 30]
    transport_rows = event_rows(tmp_path / "transport")
    decisions = [row for row in transport_rows if row["event"] == "retry_decision"]
    assert [row["retry_occurred"] for row in decisions] == [True, True, True, True, True, False]
    assert [row["retry_index"] for row in decisions] == [0, 1, 2, 3, 4, 5]
    assert len([row for row in transport_rows if row["event"] == "request"]) == 6
    assert len([row for row in transport_rows if row["event"] == "error"]) == 6
    assert all(row["exception_type"] == "URLError" for row in transport_rows if row["event"] == "error")
    assert all(secret not in json.dumps(transport_rows) for secret in ("API_SECRET", "QUERY_SECRET", "user:pass"))

    error_body = b'{"error":{"type":"rate_limit","code":"Bearer HTTP_SECRET","message":"Bearer HTTP_SECRET"}}'
    headers = Message()
    headers["Content-Type"] = "application/json"
    headers["Set-Cookie"] = "COOKIE_SECRET"
    http_error = HTTPError("https://unit.test/chat/completions", 429, "rate limited", headers, BytesIO(error_body))
    http_client = provider(ResponseQueue([http_error]), api_key="HTTP_SECRET")
    http_logger = configure_observability(http_client, tmp_path / "http", "http")
    http_instrumentation = runner.RunInstrumentation(tmp_path / "http")
    http_instrumentation.provider_boundary_logger = http_logger
    with pytest.raises(ProviderCallError) as response_error:
        runner._generate_with_transport_retry(
            http_client,
            [],
            worker_tool_definitions(),
            max_output_tokens=10,
            instrumentation=http_instrumentation,
            role="worker",
            turn=1,
        )
    assert response_error.value.details["category"] == "provider_http_error"
    assert response_error.value.details["http_status"] == 429
    assert response_error.value.details["error_code"] == "Bearer <REDACTED>"
    http_rows = event_rows(tmp_path / "http")
    assert next(row for row in http_rows if row["event"] == "response_raw")["http_status"] == 429
    assert next(row for row in http_rows if row["event"] == "retry_decision")["retry_occurred"] is False
    assert "HTTP_SECRET" not in json.dumps(http_rows)
    assert "COOKIE_SECRET" not in json.dumps(http_rows)

    parse_client = provider(ResponseQueue([]))
    parse_logger = configure_observability(parse_client, tmp_path / "parse", "parse")
    parse_client._urlopen = lambda *_args, **_kwargs: FakeResponse(b"not-json")
    with pytest.raises(ProviderCallError) as parse_error:
        parse_client.generate_with_native_tools([], worker_tool_definitions(), max_output_tokens=10)
    assert parse_error.value.details["error_type"] == "invalid_json_response"
    parse_rows = event_rows(tmp_path / "parse")
    assert [row["event"] for row in parse_rows] == ["request", "response_raw", "error"]
    assert parse_rows[-1]["http_status"] == 200


def test_logging_failure_does_not_replace_transport_exception(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class BrokenLogger(ProviderBoundaryLogger):
        def _append(self, _record: dict[str, Any]) -> None:
            raise OSError("log disk unavailable")

    monkeypatch.setattr(runner.time, "sleep", lambda _delay: None)
    queue = ResponseQueue([URLError("connection reset") for _ in range(6)])
    client = provider(queue)
    logger = BrokenLogger(tmp_path, "broken-log")
    client.enable_boundary_observability(logger, context={"run_id": "broken-log", "actor": "worker"})
    instrumentation = runner.RunInstrumentation(tmp_path)
    instrumentation.provider_boundary_logger = logger

    with pytest.raises(ProviderCallError) as failure:
        runner._generate_with_transport_retry(
            client,
            [],
            worker_tool_definitions(),
            max_output_tokens=10,
            instrumentation=instrumentation,
            role="worker",
            turn=1,
        )

    assert failure.value.details["category"] == "provider_transport_error"
    assert queue.calls == 6
    assert failure.value.details["error_type"] == "URLError"


def test_enabling_logging_does_not_change_requests_tools_or_termination(tmp_path: Path) -> None:
    first = completion(
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call-list", "type": "function", "function": {"name": "list_files", "arguments": "{}"}}
        ]},
        finish_reason="tool_calls",
        response_id="behavior-1",
    )
    second = completion(
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call-finish", "type": "function", "function": {"name": "finish_project", "arguments": "{}"}}
        ]},
        finish_reason="tool_calls",
        response_id="behavior-2",
    )
    reference_queue = ResponseQueue([first, second])
    observed_queue = ResponseQueue([first, second])
    reference = provider(reference_queue)
    observed = provider(observed_queue)
    run_root = tmp_path / "observed"
    configure_observability(observed, run_root, "behavior-test")
    reference_project = tmp_path / "reference-project"
    observed_project = tmp_path / "observed-project"
    reference_project.mkdir()
    observed_project.mkdir()
    reference_tools = WorkerTools(reference_project)
    observed_tools = WorkerTools(observed_project)

    reference_result = run_worker(reference, tmp_path / "reference", reference_tools)
    observed_result = run_worker(observed, run_root, observed_tools)

    assert reference_queue.sent_bodies == observed_queue.sent_bodies
    assert reference_tools.calls == observed_tools.calls == [("list_files", {}), ("finish_project", {})]
    assert reference_result["termination_reason"] == observed_result["termination_reason"] == "agent_completed"
    assert reference_result["model_responses"] == observed_result["model_responses"] == 2
    logged_requests = [row["serialized_body"].encode("utf-8") for row in event_rows(run_root) if row["event"] == "request"]
    assert logged_requests == observed_queue.sent_bodies
