"""Thin adapter over the already-validated DashScope backend."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GenerationResult:
    raw_model_output: str
    usage: dict[str, int | None]
    latency_sec: float
    finish_reason: str | None
    http_status: int | None


class ProviderCallError(RuntimeError):
    """Safe provider failure without credentials or request headers."""

    def __init__(self, details: dict[str, Any]) -> None:
        self.details = details
        super().__init__(str(details.get("error_type", "provider_call_failed")))


class DashScopeProvider:
    """Use the canonical OpenAI-compatible implementation without copying it."""

    provider_name = "Alibaba Cloud DashScope / OpenAI-compatible"
    endpoint_configuration_source = "canonical backend environment/.env configuration; endpoint value not recorded"
    seed_support = "not_supported"

    def __init__(self, backend_path: Path, provider_repo_root: Path, model: str, timeout_sec: float = 1200.0) -> None:
        if not backend_path.is_file():
            raise FileNotFoundError("provider backend file is unavailable")
        module_name = "pilot_1a_canonical_dashscope_backend"
        spec = importlib.util.spec_from_file_location(module_name, backend_path)
        if spec is None or spec.loader is None:
            raise ImportError("could not load the canonical provider backend")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        backend_class = getattr(module, "DashScopeBackend", None)
        if backend_class is None:
            raise ImportError("canonical provider backend has no DashScopeBackend")
        try:
            self._backend = backend_class(provider_repo_root, model=model, timeout_sec=timeout_sec)
        except Exception as exc:
            raise RuntimeError("provider configuration could not be loaded") from exc
        self.model_id = model

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_output_tokens: int | None,
    ) -> GenerationResult:
        try:
            response = self._backend.generate(
                messages,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                seed=None,
            )
        except Exception as exc:
            details: dict[str, Any] = {
                "error_type": type(exc).__name__,
                "category": "provider_error",
                "http_status": None,
            }
            raw_details = getattr(exc, "as_dict", None)
            if callable(raw_details):
                try:
                    candidate = raw_details()
                    if isinstance(candidate, dict):
                        for key in ("http_status", "category", "error_type", "error_code"):
                            if key in candidate:
                                details[key] = candidate[key]
                except Exception:
                    pass
            raise ProviderCallError(details) from None
        usage = getattr(response, "usage", {})
        safe_usage = {
            key: value if isinstance(value, int) else None
            for key, value in (
                ("prompt_tokens", usage.get("prompt_tokens")),
                ("completion_tokens", usage.get("completion_tokens")),
                ("total_tokens", usage.get("total_tokens")),
            )
        }
        return GenerationResult(
            raw_model_output=str(getattr(response, "raw_model_output", "")),
            usage=safe_usage,
            latency_sec=float(getattr(response, "latency_sec", 0.0)),
            finish_reason=getattr(response, "finish_reason", None),
            http_status=getattr(response, "http_status", None),
        )
