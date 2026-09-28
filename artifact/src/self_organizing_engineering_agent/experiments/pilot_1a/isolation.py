"""Filesystem boundary for one Pilot 1A run."""

from __future__ import annotations

import stat
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath


PUBLIC_BRIEF_FILES = (
    "case.json",
    "site.json",
    "equipment.json",
    "process_connections.json",
    "constraints.json",
)


class SandboxViolation(ValueError):
    """Raised when a tool request leaves the Agent-visible sandbox."""


def _ensure_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise SandboxViolation("path must be a non-empty relative string")
    normalized = value.replace("\\", "/")
    windows_path = PureWindowsPath(normalized)
    if windows_path.drive or windows_path.root or windows_path.anchor:
        raise SandboxViolation("absolute, drive-qualified, and UNC paths are not allowed")
    path = PurePosixPath(normalized)
    if any(part == ".." for part in path.parts):
        raise SandboxViolation("parent traversal is not allowed")
    if path == PurePosixPath("."):
        return path
    return path


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class AgentSandbox:
    """The only filesystem namespace exposed to the Agent tools."""

    run_root: Path
    agent_view: Path
    brief_root: Path
    project_root: Path

    @classmethod
    def create(cls, repo_root: Path, run_root: Path) -> "AgentSandbox":
        if run_root.exists():
            raise FileExistsError("run_id already exists")
        source_root = (repo_root / "cases" / "compressor_station_pilot_v1" / "public").resolve()
        if not source_root.is_dir():
            raise FileNotFoundError("public Pilot 0 brief is unavailable")

        run_root.mkdir(parents=True)
        agent_view = run_root / "agent_view"
        brief_root = agent_view / "brief"
        project_root = agent_view / "project"
        brief_root.mkdir(parents=True)
        project_root.mkdir(parents=True)

        for filename in PUBLIC_BRIEF_FILES:
            source = source_root / filename
            if not source.is_file():
                raise FileNotFoundError(f"public brief file is unavailable: {filename}")
            target = brief_root / filename
            shutil.copy2(source, target)
            target.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        return cls(
            run_root=run_root.resolve(),
            agent_view=agent_view.resolve(),
            brief_root=brief_root.resolve(),
            project_root=project_root.resolve(),
        )

    def _resolve_under_agent_view(self, relative_path: str) -> Path:
        path = _ensure_relative_path(relative_path)
        candidate = self.agent_view if path == PurePosixPath(".") else self.agent_view.joinpath(*path.parts)
        resolved = candidate.resolve(strict=False)
        if not _inside(self.agent_view, resolved):
            raise SandboxViolation("path leaves agent_view")
        return resolved

    def relative_display_path(self, path: Path) -> str:
        resolved = path.resolve(strict=False)
        if not _inside(self.agent_view, resolved):
            raise SandboxViolation("path leaves agent_view")
        return resolved.relative_to(self.agent_view).as_posix()

    def resolve_read_path(self, relative_path: str) -> Path:
        resolved = self._resolve_under_agent_view(relative_path)
        if not resolved.is_file():
            raise SandboxViolation("file not found")
        return resolved

    def resolve_project_path(self, relative_path: str, *, for_write: bool = False) -> Path:
        resolved = self._resolve_under_agent_view(relative_path)
        if not _inside(self.project_root, resolved):
            raise SandboxViolation("path must be inside project")
        if for_write:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            parent_resolved = resolved.parent.resolve(strict=False)
            if not _inside(self.project_root, parent_resolved):
                raise SandboxViolation("parent path leaves project")
            resolved = resolved.resolve(strict=False)
            if not _inside(self.project_root, resolved):
                raise SandboxViolation("path leaves project")
        elif not resolved.is_file():
            raise SandboxViolation("file not found")
        return resolved

    def list_files(self) -> list[str]:
        return sorted(
            path.relative_to(self.agent_view).as_posix()
            for path in self.agent_view.rglob("*")
            if path.is_file()
        )

    def read_text(self, relative_path: str, *, max_bytes: int = 2_000_000) -> str:
        path = self.resolve_read_path(relative_path)
        if path.stat().st_size > max_bytes:
            raise SandboxViolation("file is too large")
        return path.read_text(encoding="utf-8")

    def write_text(self, relative_path: str, content: str, *, max_bytes: int = 4_000_000) -> str:
        if not isinstance(content, str):
            raise SandboxViolation("content must be a string")
        if len(content.encode("utf-8")) > max_bytes:
            raise SandboxViolation("content is too large")
        path = self.resolve_project_path(relative_path, for_write=True)
        if path.exists() and path.is_dir():
            raise SandboxViolation("target is a directory")
        path.write_text(content, encoding="utf-8", newline="")
        return self.relative_display_path(path)
