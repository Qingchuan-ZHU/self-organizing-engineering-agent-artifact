"""Minimal filesystem and general-purpose Python tools for UGS-SYNTH."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..pilot_1a.docker_executor import DockerExecutor
from ..pilot_1a.isolation import AgentSandbox, SandboxViolation


APPARATUS_ID = "UGS-SYNTH apparatus v2"
APPARATUS_VERSION = "2.0.2"
APPARATUS_CHANGE_REASON = "Clarify explicit project-completion signalling through finish_project."
DEFAULT_MINIMAL_IMAGE = "self-organizing-engineering-agent/ugs-synth-minimal:python312"
CODE_MAX_BYTES = 4 * 1024 * 1024

ALLOWED_TOOL_NAMES = (
    "list_files",
    "read_file",
    "write_file",
    "execute_python",
    "finish_project",
)


def _schema(properties: dict[str, dict[str, Any]], required: tuple[str, ...] = (), extra: dict[str, Any] | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }
    if extra:
        value.update(extra)
    return value


_path = {"type": "string", "minLength": 1}
TOOL_PARAMETER_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_files": _schema({}),
    "read_file": _schema({"path": _path}, ("path",)),
    "write_file": _schema({"path": _path, "content": {"type": "string"}}, ("path", "content")),
    "execute_python": _schema(
        {"code": {"type": "string"}, "path": _path},
        extra={"oneOf": [{"required": ["code"]}, {"required": ["path"]}]},
    ),
    "finish_project": _schema({}),
}

TOOL_DESCRIPTIONS = {
    "list_files": "List files in brief/ and project/.",
    "read_file": "Read a UTF-8 text file in brief/ or project/.",
    "write_file": "Write UTF-8 text to project/.",
    "execute_python": "Run Python code or a Python file from project/ in the isolated Python container.",
    "finish_project": "Declare that project work is finished.",
}


def native_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": TOOL_DESCRIPTIONS[name],
                "parameters": deepcopy(TOOL_PARAMETER_SCHEMAS[name]),
            },
        }
        for name in ALLOWED_TOOL_NAMES
    ]


class MinimalUGSSynthTools:
    """The complete Agent-visible tool surface for apparatus v2."""

    def __init__(self, sandbox: AgentSandbox, executor: DockerExecutor) -> None:
        self.sandbox = sandbox
        self.executor = executor

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"tool_error": message}

    def dispatch(self, name: str, arguments: Any) -> dict[str, Any]:
        if name not in ALLOWED_TOOL_NAMES:
            return {"error_category": "unknown_native_tool", "tool_error": "unknown native tool"}
        if not isinstance(arguments, dict):
            return self._error("tool arguments must be an object")
        errors = list(Draft202012Validator(TOOL_PARAMETER_SCHEMAS[name]).iter_errors(arguments))
        if errors:
            return self._error("arguments do not match the published tool schema")
        return getattr(self, name)(arguments)

    def list_files(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            return self._error("list_files takes no arguments")
        return {"files": self.sandbox.list_files()}

    def read_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        relative = arguments.get("path")
        try:
            return {"path": relative.replace("\\", "/"), "content": self.sandbox.read_text(relative)}
        except (AttributeError, SandboxViolation, OSError, UnicodeError):
            return self._error("read_file is limited to readable brief and project files")

    def write_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        relative = arguments.get("path")
        content = arguments.get("content")
        try:
            stored = self.sandbox.write_text(relative, content)
        except (SandboxViolation, OSError, UnicodeError):
            return self._error("write_file is limited to project files")
        return {"path": stored, "bytes": len(content.encode("utf-8"))}

    def execute_python(self, arguments: dict[str, Any]) -> dict[str, Any]:
        code = arguments.get("code")
        project_path = arguments.get("path")
        if code is not None and project_path is not None:
            return self._error("execute_python accepts code or path, not both")
        if code is None and not isinstance(project_path, str):
            return self._error("execute_python requires code or a project Python path")
        if code is not None and (not isinstance(code, str) or len(code.encode("utf-8")) > CODE_MAX_BYTES):
            return {"status": "rejected", "exit_code": None, "stdout": "", "stderr": "code_size_limit"}

        script_path: Path | None = None
        if project_path is not None:
            try:
                script_path = self.sandbox.resolve_project_path(project_path)
            except (SandboxViolation, OSError):
                return self._error("execute_python path must be a readable project file")
        result = self.executor.execute(code=code, project_path=script_path)
        if script_path is not None:
            result["python_file"] = self.sandbox.relative_display_path(script_path)
        return result

    def finish_project(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            return self._error("finish_project takes no arguments")
        return {"status": "finish_requested"}
