"""Generic Worker and Reviewer tools for the interleaved-review treatment."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable

from jsonschema import Draft202012Validator

from ..pilot_1a.docker_executor import DockerExecutor
from ..pilot_1a.isolation import AgentSandbox, SandboxViolation, _ensure_relative_path, _inside
from ..ugs_synth_minimal.tools import (
    ALLOWED_TOOL_NAMES as BASE_WORKER_TOOL_NAMES,
    MinimalUGSSynthTools,
    TOOL_PARAMETER_SCHEMAS as BASE_WORKER_TOOL_SCHEMAS,
    native_tool_definitions,
)


MAX_REVIEW_NOTE_CHARS = 2_000
MAX_REVIEW_READ_BYTES = 2_000_000
MAX_REVIEW_WRITE_BYTES = 4_000_000

SUBMIT_FOR_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"note": {"type": "string", "maxLength": MAX_REVIEW_NOTE_CHARS}},
    "required": [],
    "additionalProperties": False,
}

_finding_schema = {
    "type": "object",
    "properties": {
        "finding_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "status": {"enum": ["confirmed_violation", "unsupported_claim", "suspected_risk", "observation"]},
        "severity": {"enum": ["critical", "high", "medium", "low"]},
        "confidence": {"enum": ["high", "medium", "low"]},
        "claim_challenged": {"type": "string", "maxLength": 8_000},
        "public_basis": {"type": "string", "maxLength": 8_000},
        "evidence": {"type": "string", "maxLength": 8_000},
        "why_it_matters": {"type": "string", "maxLength": 8_000},
        "lifecycle_status": {"enum": ["OPEN", "RESOLVED", "PERSISTS", "DISPUTED", "SUPERSEDED"]},
    },
    "required": [
        "finding_id",
        "status",
        "severity",
        "confidence",
        "claim_challenged",
        "public_basis",
        "evidence",
        "why_it_matters",
    ],
    "additionalProperties": False,
}

FINISH_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "minLength": 1, "maxLength": 8_000},
        "findings": {"type": "array", "items": _finding_schema, "maxItems": 100},
    },
    "required": ["summary", "findings"],
    "additionalProperties": False,
}

REVIEWER_TOOL_NAMES = ("list_files", "read_file", "write_file", "execute_python", "finish_review")


def worker_tool_definitions() -> list[dict[str, Any]]:
    """Return the unchanged baseline five tools plus the single treatment tool."""

    definitions = native_tool_definitions()
    definitions.append(
        {
            "type": "function",
            "function": {
                "name": "submit_for_review",
                "description": "Request an independent review of the current project state. An optional note may say what the Reviewer should focus on.",
                "parameters": deepcopy(SUBMIT_FOR_REVIEW_SCHEMA),
            },
        }
    )
    return definitions


def reviewer_tool_definitions() -> list[dict[str, Any]]:
    """The Reviewer receives only generic file, Python, and completion tools."""

    text_path = {"type": "string", "minLength": 1}
    definitions = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in read-only brief/, read-only submission/, and the persistent read-write review/ workspace.",
                "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a UTF-8 text file from brief/, submission/, or review/.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": text_path},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write UTF-8 text only in the persistent review/ workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": text_path, "content": {"type": "string"}},
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "execute_python",
                "description": "Run generic Python code or a Python file from review/ in the isolated offline container.",
                "parameters": {
                    "type": "object",
                    "properties": {"code": {"type": "string"}, "path": text_path},
                    "oneOf": [{"required": ["code"]}, {"required": ["path"]}],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "finish_review",
                "description": "Complete this review with its formal summary and findings. Findings are advisory and should not prescribe a redesign.",
                "parameters": deepcopy(FINISH_REVIEW_SCHEMA),
            },
        },
    ]
    return definitions


class InterleavedWorkerTools:
    """Delegate baseline tools unchanged and add the voluntary review interface."""

    def __init__(self, base_tools: MinimalUGSSynthTools, review_callback: Callable[[str], dict[str, Any]]) -> None:
        self.base_tools = base_tools
        self.sandbox = base_tools.sandbox
        self.review_callback = review_callback

    def dispatch(self, name: str, arguments: Any) -> dict[str, Any]:
        if name in BASE_WORKER_TOOL_NAMES:
            return self.base_tools.dispatch(name, arguments)
        if name != "submit_for_review":
            return {"error_category": "unknown_native_tool", "tool_error": "unknown native tool"}
        if not isinstance(arguments, dict) or list(Draft202012Validator(SUBMIT_FOR_REVIEW_SCHEMA).iter_errors(arguments)):
            return {"error_category": "tool_schema_violation", "tool_error": "arguments do not match the published tool schema"}
        note = arguments.get("note", "")
        try:
            return self.review_callback(note)
        except Exception as exc:
            return {"error_category": "review_runtime_error", "tool_error": type(exc).__name__}


class InterleavedReviewerExecutor(DockerExecutor):
    """Mount the submission read-only and expose the private workspace as review/."""

    def __init__(self, *, submission_root: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.submission_root = submission_root.resolve(strict=True)

    def _container_project_path(self, project_path: Path) -> str:
        resolved = project_path.resolve(strict=True)
        try:
            relative = resolved.relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError("review path leaves its mounted workspace") from exc
        return (PurePosixPath("/workspace/review") / PurePosixPath(relative.as_posix())).as_posix()

    def build_command(self, *, project_path: Path | None = None) -> list[str]:
        command = super().build_command(project_path=project_path)
        project_mount = f"type=bind,source={self.project_root},target=/workspace/project"
        replacement = f"type=bind,source={self.project_root},target=/workspace/review"
        try:
            mount_index = command.index(project_mount)
        except ValueError as exc:
            raise RuntimeError("review_workspace_mount_unavailable") from exc
        command[mount_index] = replacement
        image_index = command.index(self.image)
        command[image_index:image_index] = [
            "--mount",
            f"type=bind,source={self.submission_root},target=/workspace/submission,readonly",
        ]
        return command


class InterleavedReviewerTools:
    """Generic Reviewer tools scoped to brief/, submission/, and review/."""

    def __init__(
        self,
        *,
        sandbox: AgentSandbox,
        executor: InterleavedReviewerExecutor,
        review_number: int,
        snapshot_root: Path,
        record_formal_review: Callable[[int, dict[str, Any]], str],
    ) -> None:
        self.sandbox = sandbox
        self.executor = executor
        self.review_number = review_number
        self.snapshot_root = snapshot_root.resolve(strict=True)
        self.record_formal_review = record_formal_review
        self.formal_review: dict[str, Any] | None = None

    @staticmethod
    def _parts(value: Any) -> tuple[str, tuple[str, ...]]:
        if not isinstance(value, str) or not value or "\x00" in value:
            raise SandboxViolation("path must be a non-empty relative string")
        normalized = value.replace("\\", "/")
        windows = PureWindowsPath(normalized)
        path = PurePosixPath(normalized)
        if windows.drive or windows.root or any(part == ".." for part in path.parts):
            raise SandboxViolation("path must stay inside its named workspace")
        if not path.parts or path.parts[0] not in {"brief", "submission", "review"}:
            raise SandboxViolation("path must start with brief/, submission/, or review/")
        return path.parts[0], path.parts[1:]

    def _path(self, value: Any, *, writable: bool = False) -> Path:
        namespace, parts = self._parts(value)
        if writable and namespace != "review":
            raise SandboxViolation("write_file is limited to review/")
        roots = {
            "brief": self.sandbox.brief_root,
            "submission": self.snapshot_root,
            "review": self.sandbox.project_root,
        }
        root = roots[namespace].resolve(strict=True)
        candidate = root.joinpath(*parts).resolve(strict=False)
        if not _inside(root, candidate):
            raise SandboxViolation("path leaves its named workspace")
        if writable:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            parent = candidate.parent.resolve(strict=True)
            if not _inside(root, parent):
                raise SandboxViolation("parent path leaves review/")
        elif not candidate.is_file():
            raise SandboxViolation("file not found")
        return candidate

    def dispatch(self, name: str, arguments: Any) -> dict[str, Any]:
        if name not in REVIEWER_TOOL_NAMES:
            return {"error_category": "unknown_native_tool", "tool_error": "unknown native tool"}
        if not isinstance(arguments, dict):
            return {"error_category": "tool_schema_violation", "tool_error": "arguments must be an object"}
        schemas = {row["function"]["name"]: row["function"]["parameters"] for row in reviewer_tool_definitions()}
        if list(Draft202012Validator(schemas[name]).iter_errors(arguments)):
            return {"error_category": "tool_schema_violation", "tool_error": "arguments do not match the published tool schema"}
        if name == "list_files":
            return self.list_files()
        if name == "read_file":
            return self.read_file(arguments["path"])
        if name == "write_file":
            return self.write_file(arguments["path"], arguments["content"])
        if name == "execute_python":
            return self.execute_python(arguments)
        return self.finish_review(arguments)

    def list_files(self) -> dict[str, Any]:
        rows: list[str] = []
        roots = (
            ("brief", self.sandbox.brief_root),
            ("submission", self.snapshot_root),
            ("review", self.sandbox.project_root),
        )
        for namespace, root in roots:
            rows.extend(
                f"{namespace}/{path.relative_to(root).as_posix()}"
                for path in sorted(root.rglob("*"))
                if path.is_file()
            )
        return {"files": sorted(rows)}

    def read_file(self, value: str) -> dict[str, Any]:
        try:
            path = self._path(value)
            if path.stat().st_size > MAX_REVIEW_READ_BYTES:
                raise SandboxViolation("file is too large")
            return {"path": value.replace("\\", "/"), "content": path.read_text(encoding="utf-8")}
        except (OSError, UnicodeError, SandboxViolation):
            return {"tool_error": "read_file is limited to readable brief, submission, and review files"}

    def write_file(self, value: str, content: str) -> dict[str, Any]:
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_REVIEW_WRITE_BYTES:
            return {"tool_error": "write_file content is invalid or too large"}
        try:
            path = self._path(value, writable=True)
            if path.exists() and path.is_dir():
                raise SandboxViolation("target is a directory")
            path.write_text(content, encoding="utf-8", newline="")
            return {"path": value.replace("\\", "/"), "bytes": len(content.encode("utf-8"))}
        except (OSError, UnicodeError, SandboxViolation):
            return {"tool_error": "write_file is limited to review/"}

    def execute_python(self, arguments: dict[str, Any]) -> dict[str, Any]:
        code = arguments.get("code")
        value = arguments.get("path")
        if code is not None and value is not None:
            return {"tool_error": "execute_python accepts code or path, not both"}
        if code is None and not isinstance(value, str):
            return {"tool_error": "execute_python requires code or a review/ Python path"}
        if code is not None and len(code.encode("utf-8")) > MAX_REVIEW_WRITE_BYTES:
            return {"status": "rejected", "exit_code": None, "stdout": "", "stderr": "code_size_limit"}
        project_path: Path | None = None
        if value is not None:
            try:
                namespace, _ = self._parts(value)
                if namespace != "review":
                    raise SandboxViolation("Python scripts must be in review/")
                project_path = self._path(value)
            except (OSError, SandboxViolation):
                return {"tool_error": "execute_python path must be a readable review/ file"}
        result = self.executor.execute(code=code, project_path=project_path)
        if project_path is not None:
            result["python_file"] = project_path.relative_to(self.sandbox.project_root).as_posix()
        return result

    def finish_review(self, formal_review: dict[str, Any]) -> dict[str, Any]:
        finding_ids = [finding["finding_id"] for finding in formal_review["findings"]]
        if len(finding_ids) != len(set(finding_ids)):
            return {"error_category": "duplicate_finding_ids", "tool_error": "finding_id values must be unique within one review"}
        self.formal_review = deepcopy(formal_review)
        result_hash = self.record_formal_review(self.review_number, self.formal_review)
        return {
            "status": "finish_requested",
            "review_number": self.review_number,
            "formal_review_sha256": result_hash,
        }
