"""Direct DeepSeek Chat Completions adapter for bounded Pilot 1A work.

The adapter deliberately accepts exactly one model identity.  It uses the
OpenAI-compatible HTTP shape without depending on the optional OpenAI SDK, so
unit tests and the preflight runner share the same request/response boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .provider import ProviderCallError


DEEPSEEK_MODEL = "deepseek-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"
THINKING_TYPE = "enabled"
REASONING_EFFORT = "high"
FALLBACK_MODELS: tuple[str, ...] = ()

_ENV_KEYS = ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL")


@dataclass(frozen=True)
class DeepSeekGenerationResult:
    """DeepSeek-specific result; the frozen Pilot 1A provider type is untouched."""

    raw_model_output: str
    usage: dict[str, int | None]
    latency_sec: float
    finish_reason: str | None
    http_status: int | None
    returned_model: str | None = None
    reasoning_content_present: bool = False
    reasoning_content_length: int = 0
    assistant_message: dict[str, Any] | None = None
    native_tool_calls: list[dict[str, Any]] | None = None

    @property
    def visible_content(self) -> str:
        return self.raw_model_output


def _parse_env_file(path: Path) -> dict[str, str]:
    """Read only the three provider settings needed by this adapter."""

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in _ENV_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _configured_value(
    name: str,
    explicit: str | None,
    file_values: Mapping[str, str],
) -> str:
    if explicit is not None and explicit.strip():
        return explicit.strip()
    process_value = os.getenv(name, "").strip()
    if process_value:
        return process_value
    return file_values.get(name, "").strip()


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _nested(mapping: Any, *keys: str) -> Any:
    current = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _usage_from_response(raw_usage: Any) -> dict[str, int | None]:
    """Map DeepSeek raw usage fields without estimating absent values."""

    prompt_tokens = _as_int(_nested(raw_usage, "prompt_tokens"))
    completion_tokens = _as_int(_nested(raw_usage, "completion_tokens"))
    total_tokens = _as_int(_nested(raw_usage, "total_tokens"))
    cached_tokens = _as_int(_nested(raw_usage, "prompt_tokens_details", "cached_tokens"))
    if cached_tokens is None:
        cached_tokens = _as_int(_nested(raw_usage, "prompt_cache_hit_tokens"))
    cache_hit_tokens = _as_int(_nested(raw_usage, "prompt_cache_hit_tokens"))
    cache_miss_tokens = _as_int(_nested(raw_usage, "prompt_cache_miss_tokens"))
    reasoning_tokens = _as_int(
        _nested(raw_usage, "completion_tokens_details", "reasoning_tokens")
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cached_tokens": cached_tokens,
        "cached_input_tokens": cached_tokens,
        "prompt_cache_hit_tokens": cache_hit_tokens,
        "prompt_cache_miss_tokens": cache_miss_tokens,
    }


def _safe_provider_error_fields(
    body: bytes,
    *,
    known_secrets: tuple[str, ...] = (),
) -> dict[str, str]:
    """Keep error classification while excluding provider messages and secrets."""

    try:
        parsed = json.loads(body.decode("utf-8", errors="replace"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    error = parsed.get("error") if isinstance(parsed, dict) else None
    if not isinstance(error, dict):
        return {}
    result: dict[str, str] = {}
    for source_key, target_key in (("type", "provider_error_type"), ("code", "error_code")):
        value = error.get(source_key)
        if isinstance(value, str) and value:
            safe_value = value
            for secret in known_secrets:
                if secret:
                    safe_value = safe_value.replace(secret, "<REDACTED>")
            safe_value = re.sub(r"(?i)\bBearer\s+\S+", "Bearer <REDACTED>", safe_value)
            safe_value = re.sub(
                r"(?i)([?&](?:api[_-]?key|app[_-]?key|key|token|access[_-]?token|secret|password)=)[^&#\s]+",
                r"\1<REDACTED>",
                safe_value,
            )
            safe_value = re.sub(
                r"(?i)\b(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|session[_-]?token|"
                r"token|cookie|client[_-]?secret|password|secret)\b\s*[:=]\s*\S+",
                "<REDACTED>",
                safe_value,
            )
            safe_value = re.sub(
                r"([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+:[^/@\s]+@",
                r"\1<REDACTED>@",
                safe_value,
            )
            result[target_key] = safe_value[:120]
    return result


def classify_finish_reason(finish_reason: str | None, visible_content: str) -> str:
    """Classify the observable completion boundary without parsing reasoning."""

    if finish_reason == "length":
        return "truncation_output_budget"
    if not visible_content:
        return "empty_visible_content"
    if finish_reason == "stop":
        return "completed"
    return "provider_finish_reason_other"


def decode_chat_completion(
    payload: Mapping[str, Any],
    *,
    latency_sec: float,
    http_status: int | None,
) -> DeepSeekGenerationResult:
    """Decode one response and expose only visible content to the runner."""

    returned_model = payload.get("model")
    if not isinstance(returned_model, str) or not returned_model:
        raise ProviderCallError(
            {
                "error_type": "missing_model_field",
                "category": "malformed_response",
                "http_status": http_status,
            }
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderCallError(
            {
                "error_type": "missing_choices",
                "category": "malformed_response",
                "http_status": http_status,
            }
        )
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ProviderCallError(
            {
                "error_type": "missing_message",
                "category": "malformed_response",
                "http_status": http_status,
            }
        )
    visible_content = message.get("content")
    if visible_content is not None and not isinstance(visible_content, str):
        raise ProviderCallError(
            {
                "error_type": "non_string_visible_content",
                "category": "malformed_response",
                "http_status": http_status,
            }
        )
    if visible_content is None:
        visible_content = ""
    tool_calls = message.get("tool_calls")
    if tool_calls is not None and not isinstance(tool_calls, list):
        raise ProviderCallError(
            {
                "error_type": "non_list_tool_calls",
                "category": "malformed_response",
                "http_status": http_status,
            }
        )
    reasoning_content = message.get("reasoning_content")
    reasoning_length = len(reasoning_content) if isinstance(reasoning_content, str) else 0
    finish_reason = choice.get("finish_reason")
    if finish_reason is not None and not isinstance(finish_reason, str):
        finish_reason = None
    return DeepSeekGenerationResult(
        raw_model_output=visible_content,
        usage=_usage_from_response(payload.get("usage")),
        latency_sec=latency_sec,
        finish_reason=finish_reason,
        http_status=http_status,
        returned_model=returned_model,
        reasoning_content_present=reasoning_length > 0,
        reasoning_content_length=reasoning_length,
        assistant_message=dict(message),
        native_tool_calls=[call for call in tool_calls if isinstance(call, dict)] if tool_calls is not None else None,
    )


class DeepSeekProvider:
    """Strict `deepseek-flash` provider with no alias fallback."""

    provider_name = "DeepSeek direct API / OpenAI-compatible"
    endpoint_configuration_source = "DEEPSEEK_BASE_URL or default; endpoint value not persisted"
    seed_support = "not_supported"
    model_id = DEEPSEEK_MODEL
    thinking = THINKING_TYPE
    reasoning_effort = REASONING_EFFORT
    temperature_control = "not_used"
    fallback_models = FALLBACK_MODELS
    retry_policy = "none"

    def __init__(
        self,
        *,
        model: str = DEEPSEEK_MODEL,
        base_url: str | None = None,
        api_key: str | None = None,
        env_file: Path | None = None,
        timeout_sec: float = 180.0,
        urlopen_fn: Callable[..., Any] | None = None,
    ) -> None:
        if model != DEEPSEEK_MODEL:
            raise ValueError(f"DeepSeek preflight model is fixed to {DEEPSEEK_MODEL}")
        if timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive")
        file_values = _parse_env_file(env_file) if env_file is not None else {}
        configured_model = _configured_value("DEEPSEEK_MODEL", None, file_values)
        if configured_model and configured_model != model:
            raise ValueError("configured DeepSeek model does not match the fixed model")
        configured_key = _configured_value("DEEPSEEK_API_KEY", api_key, file_values)
        if not configured_key:
            raise RuntimeError("DeepSeek API key is not configured")

        if api_key is not None and api_key.strip():
            credential_source = {"kind": "explicit_argument"}
        elif os.getenv("DEEPSEEK_API_KEY", "").strip():
            credential_source = {"kind": "process_environment", "name": "DEEPSEEK_API_KEY"}
        elif file_values.get("DEEPSEEK_API_KEY", "").strip() and env_file is not None:
            credential_source = {"kind": "env_file", "path": str(env_file.resolve())}
        else:
            credential_source = {"kind": "configured"}

        if os.getenv("DEEPSEEK_MODEL", "").strip():
            model_configuration_source = "process_environment"
        elif file_values.get("DEEPSEEK_MODEL", "").strip():
            model_configuration_source = "env_file"
        else:
            model_configuration_source = "provider_default"

        self._api_key = configured_key
        self.base_url = _configured_value("DEEPSEEK_BASE_URL", base_url, file_values) or DEFAULT_BASE_URL
        self.configured_model = configured_model or model
        self.effective_model = model
        self.model_configuration_source = model_configuration_source
        self.credential_source = credential_source
        self.credential_configured = True
        self.endpoint_host = urlsplit(self.base_url).hostname or "configured_non_url"
        self.model_id = self.effective_model
        self.timeout_sec = timeout_sec
        self._urlopen = urlopen_fn or urlopen
        self._boundary_observer: Callable[[dict[str, Any]], int | None] | None = None
        self._boundary_context: dict[str, Any] = {}

    def enable_boundary_observability(
        self,
        observer: Callable[[dict[str, Any]], int | None],
        *,
        context: Mapping[str, Any],
    ) -> None:
        """Attach an optional, best-effort observer without changing requests."""

        self._boundary_observer = observer
        self._boundary_context = dict(context)

    def set_boundary_context(self, context: Mapping[str, Any]) -> None:
        """Set per-call metadata used only by the optional observer."""

        base = {key: value for key, value in self._boundary_context.items() if key in {"run_id", "actor"}}
        self._boundary_context = {**base, **dict(context)}

    def _observe_boundary(self, event: str, **fields: Any) -> int | None:
        observer = self._boundary_observer
        if observer is None:
            return None
        try:
            record = {
                "event": event,
                "context": dict(self._boundary_context),
                "provider": self.provider_name,
                "model": self.model_id,
                "endpoint_identifier": self._endpoint_identifier(),
                "redaction_secrets": (self._api_key,),
                **fields,
            }
            return observer(record)
        except Exception:
            # Evidence writing must never replace a provider result or exception.
            return None

    def _endpoint_identifier(self) -> str:
        parts = urlsplit(self.base_url)
        hostname = parts.hostname or "configured_non_url"
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        if parts.port is not None:
            hostname = f"{hostname}:{parts.port}"
        path = (parts.path.rstrip("/") + "/chat/completions") if parts.path else "/chat/completions"
        return f"{parts.scheme or 'https'}://{hostname}{path}"

    def request_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "requested_model": self.model_id,
            "base_url_host": self.base_url.split("/", 3)[2] if "://" in self.base_url else "configured_non_url",
            "thinking": {"type": self.thinking},
            "reasoning_effort": self.reasoning_effort,
            "temperature_control": self.temperature_control,
            "max_token_parameter": "max_tokens",
            "native_tool_calling": "not_used",
            "fallback_models": list(self.fallback_models),
            "credential_source": "DEEPSEEK_API_KEY; value not persisted",
        }

    def build_request_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        max_output_tokens: int | None,
    ) -> dict[str, Any]:
        if max_output_tokens is not None and max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "reasoning_effort": self.reasoning_effort,
            "thinking": {"type": self.thinking},
        }
        if max_output_tokens is not None:
            payload["max_tokens"] = max_output_tokens
        return payload

    def build_native_tool_request_payload(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        max_output_tokens: int | None,
    ) -> dict[str, Any]:
        if not tools:
            raise ValueError("native tool requests require at least one tool definition")
        payload = self.build_request_payload(messages, max_output_tokens=max_output_tokens)
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
        return payload

    def _send_payload(self, request_payload: dict[str, Any]) -> DeepSeekGenerationResult:
        serialized_body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=serialized_body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        request_index = self._observe_boundary(
            "request",
            http_method=request.get_method(),
            request_headers=dict(request.header_items()),
            serialized_body=serialized_body,
            serialized_body_sha256=hashlib.sha256(serialized_body).hexdigest(),
            serialized_body_byte_length=len(serialized_body),
        )
        started = time.perf_counter()
        try:
            with self._urlopen(request, timeout=self.timeout_sec) as response:
                http_status = response.getcode()
                body = response.read()
                response_headers = dict(response.headers.items()) if getattr(response, "headers", None) is not None else {}
            received_elapsed = time.perf_counter() - started
            self._observe_boundary(
                "response_raw",
                request_index=request_index,
                http_status=http_status,
                response_headers=response_headers,
                raw_body=body,
                raw_body_sha256=hashlib.sha256(body).hexdigest(),
                raw_body_byte_length=len(body),
            )
        except HTTPError as exc:
            body = exc.read()
            self._observe_boundary(
                "response_raw",
                request_index=request_index,
                http_status=exc.code,
                response_headers=dict(exc.headers.items()) if exc.headers is not None else {},
                raw_body=body,
                raw_body_sha256=hashlib.sha256(body).hexdigest(),
                raw_body_byte_length=len(body),
            )
            self._observe_boundary(
                "error",
                request_index=request_index,
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                http_status=exc.code,
                retry_index=self._boundary_context.get("retry_index"),
                retry_occurred=None,
            )
            details: dict[str, Any] = {
                "error_type": type(exc).__name__,
                "category": "provider_http_error",
                "http_status": exc.code,
                "requested_model": self.model_id,
            }
            details.update(_safe_provider_error_fields(body, known_secrets=(self._api_key,)))
            raise ProviderCallError(details) from None
        except (TimeoutError, URLError, OSError, HTTPException) as exc:
            self._observe_boundary(
                "error",
                request_index=request_index,
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                http_status=None,
                retry_index=self._boundary_context.get("retry_index"),
                retry_occurred=None,
            )
            raise ProviderCallError(
                {
                    "error_type": type(exc).__name__,
                    "category": "provider_transport_error",
                    "http_status": None,
                    "requested_model": self.model_id,
                }
            ) from exc
        parse_started = time.perf_counter()
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._observe_boundary(
                "error",
                request_index=request_index,
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                http_status=http_status,
                retry_index=self._boundary_context.get("retry_index"),
                retry_occurred=False,
            )
            raise ProviderCallError(
                {
                    "error_type": "invalid_json_response",
                    "category": "malformed_response",
                    "http_status": http_status,
                    "requested_model": self.model_id,
                }
            ) from None
        provider_latency_sec = received_elapsed + (time.perf_counter() - parse_started)
        if not isinstance(payload, dict):
            self._observe_boundary(
                "error",
                request_index=request_index,
                exception_type="TypeError",
                exception_message="provider response JSON is not an object",
                http_status=http_status,
                retry_index=self._boundary_context.get("retry_index"),
                retry_occurred=False,
            )
            raise ProviderCallError(
                {
                    "error_type": "non_object_response",
                    "category": "malformed_response",
                    "http_status": http_status,
                    "requested_model": self.model_id,
                }
            )
        provider_response_id = payload.get("id")
        self._observe_boundary(
            "response_parsed",
            request_index=request_index,
            http_status=http_status,
            provider_response_id=provider_response_id,
            parsed_provider_object=payload,
        )
        try:
            generation = decode_chat_completion(
                payload,
                latency_sec=provider_latency_sec,
                http_status=http_status,
            )
        except ProviderCallError as exc:
            self._observe_boundary(
                "error",
                request_index=request_index,
                exception_type=exc.details.get("error_type", type(exc).__name__),
                exception_message=exc.details.get("error_type", "provider response decode failed"),
                http_status=http_status,
                retry_index=self._boundary_context.get("retry_index"),
                retry_occurred=False,
            )
            details = dict(exc.details)
            details.setdefault("requested_model", self.model_id)
            raise ProviderCallError(details) from None
        self._observe_boundary(
            "runtime_assistant",
            request_index=request_index,
            http_status=http_status,
            provider_response_id=provider_response_id,
            finish_reason=generation.finish_reason,
            content=generation.raw_model_output,
            reasoning_content=(generation.assistant_message or {}).get("reasoning_content"),
            tool_calls=(generation.assistant_message or {}).get("tool_calls"),
            usage=generation.usage,
            runtime_assistant_message=generation.assistant_message,
        )
        return generation

    def generate(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_output_tokens: int | None,
    ) -> DeepSeekGenerationResult:
        del temperature
        request_payload = self.build_request_payload(
            messages,
            max_output_tokens=max_output_tokens,
        )
        return self._send_payload(request_payload)

    def generate_with_native_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        max_output_tokens: int | None,
    ) -> DeepSeekGenerationResult:
        """Send a native function-call request without altering provider history."""

        request_payload = self.build_native_tool_request_payload(
            messages,
            tools,
            max_output_tokens=max_output_tokens,
        )
        return self._send_payload(request_payload)
