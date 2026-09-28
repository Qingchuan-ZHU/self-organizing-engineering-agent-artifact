"""Construction of the isolated UGS-SYNTH apparatus v2 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..pilot_1a.docker_executor import DockerExecutor
from ..pilot_1a.isolation import AgentSandbox
from .isolation import create_minimal_sandbox
from .tools import DEFAULT_MINIMAL_IMAGE, MinimalUGSSynthTools


@dataclass(frozen=True)
class MinimalRuntime:
    sandbox: AgentSandbox
    executor: DockerExecutor
    tools: MinimalUGSSynthTools


def create_minimal_runtime(
    repo_root: Path,
    run_root: Path,
    *,
    image: str = DEFAULT_MINIMAL_IMAGE,
) -> MinimalRuntime:
    sandbox = create_minimal_sandbox(repo_root, run_root)
    executor = DockerExecutor(
        image=image,
        brief_root=sandbox.brief_root,
        project_root=sandbox.project_root,
    )
    return MinimalRuntime(sandbox=sandbox, executor=executor, tools=MinimalUGSSynthTools(sandbox, executor))
