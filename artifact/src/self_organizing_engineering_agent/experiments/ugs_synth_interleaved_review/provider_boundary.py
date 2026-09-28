"""Append-only, secret-safe provider-boundary evidence for this treatment."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOGGING_SCHEMA_VERSION = "1"
REDACTION_POLICY_VERSION = "1"
RAW_RESPONSE_CAPTURE_LEVEL = "http_raw_body_pre_parser_redacted"

_SAFE_HEADERS = {
    "accept",
    "content-type",
    "content-length",
    "date",
    "user-agent",
    "request-id",
    "x-request-id",
    "x-deepseek-request-id",
}
_SECRET_KEY = re.compile(
    r"(?i)(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|session[_-]?token|"
    r"cookie|set-cookie|client[_-]?secret|password|secret)"
)
_SENSITIVE_JSON_FIELD = re.compile(
    r"(?i)(\"[^\"]*(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|session[_-]?token|"
    r"cookie|set-cookie|client[_-]?secret|password|secret)[^\"]*\"\s*:\s*)(\"(?:\\.|[^\"])*\"|[^,}\s]+)"
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|session[_-]?token|"
    r"token|cookie|client[_-]?secret|password|secret)\b\s*[:=]\s*(\"[^\"]*\"|'[^']*'|[^\s,;}\]]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:api[_-]?key|app[_-]?key|key|token|access[_-]?token|refresh[_-]?token|"
    r"session[_-]?token|secret|client[_-]?secret|password|signature|sig)=)[^&#\s]+"
)
_URL_CREDENTIALS = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+:[^/@\s]+@")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _redact_text(value: str, known_secrets: tuple[str, ...]) -> tuple[str, bool]:
    redacted = value
    for secret in known_secrets:
        if secret:
            redacted = redacted.replace(secret, "<REDACTED>")
    redacted = _SENSITIVE_JSON_FIELD.sub(r'\1"<REDACTED>"', redacted)
    redacted = _BEARER.sub("Bearer <REDACTED>", redacted)
    redacted = _SECRET_ASSIGNMENT.sub("<REDACTED>", redacted)
    redacted = _QUERY_SECRET.sub(r"\1<REDACTED>", redacted)
    redacted = _URL_CREDENTIALS.sub(r"\1<REDACTED>@", redacted)
    return redacted, redacted != value


def _redact_value(value: Any, known_secrets: tuple[str, ...], *, key: str | None = None) -> Any:
    if key is not None and _SECRET_KEY.search(key):
        return "<REDACTED>"
    if isinstance(value, dict):
        return {
            str(child_key): _redact_value(child_value, known_secrets, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, known_secrets) for item in value]
    if isinstance(value, str):
        return _redact_text(value, known_secrets)[0]
    return value


def sanitize_headers(
    headers: dict[str, Any],
    *,
    known_secrets: tuple[str, ...] = (),
) -> dict[str, str]:
    """Retain only explicitly safe HTTP headers; unknown fields are omitted."""

    result: dict[str, str] = {}
    for name, value in headers.items():
        normalized_name = str(name).strip().lower()
        if normalized_name in _SAFE_HEADERS and isinstance(value, (str, int, float)):
            result[normalized_name] = _redact_text(str(value), known_secrets)[0]
    return result


class ProviderBoundaryLogger:
    """Write one ordered JSONL event per observable provider-boundary layer."""

    def __init__(self, run_root: Path, run_id: str) -> None:
        self.run_root = run_root
        self.run_id = run_id
        self.path = run_root / "provider_logs" / "events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._next_request_index = 1
        self._last_request_index: dict[str, int] = {}
        self._last_response_index: dict[str, int] = {}

    def latest_request_index(self, actor: str) -> int | None:
        with self._lock:
            return self._last_request_index.get(actor)

    def latest_response_index(self, actor: str) -> int | None:
        with self._lock:
            return self._last_response_index.get(actor)

    def record_retry_decision(
        self,
        *,
        request_index: int | None,
        actor: str,
        retry_index: int,
        retry_occurred: bool,
    ) -> None:
        if request_index is None:
            return
        self({
            "event": "retry_decision",
            "request_index": request_index,
            "context": {"actor": actor, "retry_index": retry_index},
            "retry_occurred": retry_occurred,
        })

    def __call__(self, event: dict[str, Any]) -> int | None:
        event_name = event.get("event")
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        actor = context.get("actor")
        secrets_value = event.get("redaction_secrets", ())
        known_secrets = tuple(value for value in secrets_value if isinstance(value, str)) if isinstance(secrets_value, (tuple, list)) else ()
        clean = {
            key: value
            for key, value in event.items()
            if key not in {"redaction_secrets", "context"}
        }
        clean_context = _redact_value(context, known_secrets)
        request_index = event.get("request_index")
        if event_name == "request":
            with self._lock:
                request_index = self._next_request_index
                self._next_request_index += 1
                if isinstance(actor, str):
                    self._last_request_index[actor] = request_index
        if not isinstance(request_index, int):
            return None

        common = {
            "timestamp": _utc_now(),
            "run_id": self.run_id,
            "request_index": request_index,
            "actor": actor,
            "provider": event.get("provider"),
            "model": event.get("model"),
            "turn": clean_context.get("turn"),
            "review_number": clean_context.get("review_number"),
            "attempt_index": clean_context.get("attempt_index"),
            "retry_index": clean_context.get("retry_index"),
        }

        if event_name == "request":
            raw_body = event.get("serialized_body")
            raw_body = raw_body if isinstance(raw_body, bytes) else b""
            body_text = raw_body.decode("utf-8", errors="replace")
            safe_body_text, redacted_body = _redact_text(body_text, known_secrets)
            try:
                body_object = json.loads(body_text)
            except (UnicodeDecodeError, json.JSONDecodeError):
                body_object = None
            safe_body_object = _redact_value(body_object, known_secrets) if isinstance(body_object, dict) else body_object
            if safe_body_object != body_object and isinstance(safe_body_object, dict):
                safe_body_text = json.dumps(safe_body_object, ensure_ascii=False)
                redacted_body = True
            if isinstance(body_object, dict):
                messages = body_object.get("messages")
                messages = messages if isinstance(messages, list) else []
            else:
                messages = []
            tool_call_ids: list[str] = []
            tool_result_ids: list[str] = []
            for message in messages:
                if not isinstance(message, dict):
                    continue
                calls = message.get("tool_calls")
                if isinstance(calls, list):
                    tool_call_ids.extend(
                        call["id"] for call in calls
                        if isinstance(call, dict) and isinstance(call.get("id"), str)
                    )
                if message.get("role") == "tool" and isinstance(message.get("tool_call_id"), str):
                    tool_result_ids.append(message["tool_call_id"])
            continuation = None
            continuation_index = clean_context.get("continuation_index")
            if isinstance(continuation_index, int):
                replay = clean_context.get("assistant_message_replayed")
                request_messages = _redact_value(messages, known_secrets)
                safe_replay = _redact_value(replay, known_secrets)
                last_message = messages[-1] if messages and isinstance(messages[-1], dict) else None
                continuation = {
                    "continuation_index": continuation_index,
                    "triggering_response_index": clean_context.get("triggering_response_index"),
                    "reason": clean_context.get("continuation_reason"),
                    "assistant_message_replayed": safe_replay,
                    "new_request_messages": request_messages,
                    "reasoning_content_preserved": self._field_preserved(replay, last_message, "reasoning_content"),
                    "content_preserved": self._field_preserved(replay, last_message, "content"),
                    "tool_calls_preserved": self._field_preserved(replay, last_message, "tool_calls"),
                }
            record = {
                **common,
                "event": "request",
                "context": _redact_value(clean_context, known_secrets),
                "endpoint_identifier": _redact_text(str(clean.get("endpoint_identifier", "")), known_secrets)[0],
                "http_method": clean.get("http_method"),
                "request_headers": sanitize_headers(clean.get("request_headers", {}), known_secrets=known_secrets),
                "serialized_body": safe_body_text,
                "serialized_body_sha256": clean.get("serialized_body_sha256") or hashlib.sha256(raw_body).hexdigest(),
                "serialized_body_byte_length": clean.get("serialized_body_byte_length", len(raw_body)),
                "serialized_body_redacted": redacted_body,
                "preceding_tool_call_ids": tool_call_ids,
                "preceding_tool_result_ids": tool_result_ids,
                "continuation": continuation,
                "logging_schema_version": LOGGING_SCHEMA_VERSION,
                "redaction_policy_version": REDACTION_POLICY_VERSION,
            }
            self._append(record)
            return request_index

        if event_name == "response_raw":
            raw_body = event.get("raw_body")
            raw_body = raw_body if isinstance(raw_body, bytes) else b""
            body_text = raw_body.decode("utf-8", errors="replace")
            safe_body_text, redacted_body = _redact_text(body_text, known_secrets)
            record = {
                **common,
                "event": "response_raw",
                "response_headers": sanitize_headers(clean.get("response_headers", {}), known_secrets=known_secrets),
                "http_status": clean.get("http_status"),
                "raw_body": safe_body_text,
                "raw_body_sha256": clean.get("raw_body_sha256") or hashlib.sha256(raw_body).hexdigest(),
                "raw_body_byte_length": clean.get("raw_body_byte_length", len(raw_body)),
                "raw_body_redacted": redacted_body,
                "raw_response_capture_level": RAW_RESPONSE_CAPTURE_LEVEL,
            }
            self._append(record)
            return request_index

        if event_name == "response_parsed":
            record = {
                **common,
                "event": "response_parsed",
                "http_status": clean.get("http_status"),
                "provider_response_id": _redact_value(clean.get("provider_response_id"), known_secrets),
                "parsed_provider_object": _redact_value(clean.get("parsed_provider_object"), known_secrets),
            }
            self._append(record)
            if isinstance(actor, str):
                with self._lock:
                    self._last_response_index[actor] = request_index
            return request_index

        if event_name == "runtime_assistant":
            record = {
                **common,
                "event": "runtime_assistant",
                "http_status": clean.get("http_status"),
                "provider_response_id": _redact_value(clean.get("provider_response_id"), known_secrets),
                "finish_reason": clean.get("finish_reason"),
                "content": _redact_value(clean.get("content"), known_secrets),
                "reasoning_content": _redact_value(clean.get("reasoning_content"), known_secrets),
                "tool_calls": _redact_value(clean.get("tool_calls"), known_secrets),
                "usage": clean.get("usage"),
                "runtime_assistant_message": _redact_value(clean.get("runtime_assistant_message"), known_secrets),
            }
            self._append(record)
            return request_index

        if event_name in {"error", "retry_decision"}:
            record = {
                **common,
                **_redact_value(clean, known_secrets),
                "event": event_name,
                "context": _redact_value(clean_context, known_secrets),
            }
            self._append(record)
            return request_index
        return None

    @staticmethod
    def _field_preserved(original: Any, replayed: Any, field: str) -> bool | None:
        if not isinstance(original, dict) or field not in original:
            return None
        return isinstance(replayed, dict) and replayed.get(field) == original[field]

    def _append(self, record: dict[str, Any]) -> None:
        serialized = json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized + "\n")
