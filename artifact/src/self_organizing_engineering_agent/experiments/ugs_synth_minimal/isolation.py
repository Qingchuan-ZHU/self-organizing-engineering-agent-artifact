"""Filesystem setup for the UGS-SYNTH minimal runtime."""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

from ..pilot_1a.isolation import AgentSandbox


def create_minimal_sandbox(repo_root: Path, run_root: Path) -> AgentSandbox:
    if run_root.exists():
        raise FileExistsError("run directory already exists")

    source_root = (repo_root / "cases" / "ugs_synth_d01" / "public").resolve()
    if not source_root.is_dir():
        raise FileNotFoundError("public engineering world is unavailable")

    public_files: list[Path] = []
    for source in source_root.rglob("*"):
        if source.is_symlink():
            raise ValueError("public engineering world must not contain symlinks")
        if source.is_file():
            resolved = source.resolve(strict=True)
            if source_root not in resolved.parents:
                raise ValueError("public file leaves the public engineering world")
            public_files.append(source)

    run_root.mkdir(parents=True)
    agent_view = run_root / "agent_view"
    brief_root = agent_view / "brief"
    project_root = agent_view / "project"
    brief_root.mkdir(parents=True)
    project_root.mkdir()

    for source in public_files:
        target = brief_root / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    for directory in sorted((item for item in brief_root.rglob("*") if item.is_dir()), reverse=True):
        directory.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    brief_root.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

    return AgentSandbox(
        run_root=run_root.resolve(),
        agent_view=agent_view.resolve(),
        brief_root=brief_root.resolve(),
        project_root=project_root.resolve(),
    )
