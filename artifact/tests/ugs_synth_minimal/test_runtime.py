from __future__ import annotations

import os
import re
import json
from pathlib import Path

import pytest

from self_organizing_engineering_agent.experiments.pilot_1a.docker_executor import DockerExecutor
from self_organizing_engineering_agent.experiments.ugs_synth_minimal.isolation import create_minimal_sandbox
from self_organizing_engineering_agent.experiments.ugs_synth_minimal.runtime import create_minimal_runtime
from self_organizing_engineering_agent.experiments.ugs_synth_minimal.tools import (
    ALLOWED_TOOL_NAMES,
    APPARATUS_CHANGE_REASON,
    APPARATUS_VERSION,
    DEFAULT_MINIMAL_IMAGE,
    TOOL_PARAMETER_SCHEMAS,
    MinimalUGSSynthTools,
    native_tool_definitions,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def execute(self, *, code: str | None = None, project_path: Path | None = None) -> dict[str, object]:
        self.calls.append({"code": code, "project_path": project_path})
        return {"status": "completed", "exit_code": 0, "stdout": "ok\n", "stderr": "", "timeout": False}


def _make_tools(tmp_path: Path) -> tuple[object, MinimalUGSSynthTools, FakeExecutor]:
    sandbox = create_minimal_sandbox(REPO_ROOT, tmp_path / "run")
    executor = FakeExecutor()
    return sandbox, MinimalUGSSynthTools(sandbox, executor), executor


def test_agent_visible_tools_are_exactly_the_minimal_allowlist() -> None:
    definitions = native_tool_definitions()
    names = [row["function"]["name"] for row in definitions]

    assert tuple(names) == ALLOWED_TOOL_NAMES
    assert set(names) == {"list_files", "read_file", "write_file", "execute_python", "finish_project"}
    assert set(TOOL_PARAMETER_SCHEMAS) == set(ALLOWED_TOOL_NAMES)
    assert all("check_" not in name and name not in {"route_connection", "render_design", "evaluate_design"} for name in names)


def test_file_tools_keep_brief_read_only_and_project_persistent(tmp_path: Path) -> None:
    sandbox, tools, _ = _make_tools(tmp_path)

    listed = tools.dispatch("list_files", {})["files"]
    assert "brief/final_delivery_contract.json" in listed
    assert not any("hidden" in name or "best_known" in name or "/schemas/" in name for name in listed)
    assert not any(name.startswith("project/") for name in listed)
    assert tools.dispatch("read_file", {"path": "brief/project_requirements.json"})["content"]
    assert "tool_error" in tools.dispatch("write_file", {"path": "brief/blocked.txt", "content": "x"})
    assert "tool_error" in tools.dispatch("read_file", {"path": "../outside.txt"})

    result = tools.dispatch("write_file", {"path": "project/notes/work.txt", "content": "saved"})
    assert result["path"] == "project/notes/work.txt"
    assert (sandbox.project_root / "notes" / "work.txt").read_text(encoding="utf-8") == "saved"
    assert "project/notes/work.txt" in tools.dispatch("list_files", {})["files"]


def test_execute_python_uses_only_the_container_executor(tmp_path: Path) -> None:
    _, tools, executor = _make_tools(tmp_path)

    result = tools.dispatch("execute_python", {"code": "print('ok')"})

    assert result["status"] == "completed"
    assert executor.calls == [{"code": "print('ok')", "project_path": None}]
    assert tools.dispatch("route_connection", {})["error_category"] == "unknown_native_tool"
    assert tools.dispatch("evaluate_design", {})["error_category"] == "unknown_native_tool"


def test_finish_project_only_returns_a_control_signal(tmp_path: Path) -> None:
    _, tools, _ = _make_tools(tmp_path)

    assert tools.dispatch("finish_project", {}) == {"status": "finish_requested"}


def test_docker_executor_declares_the_isolation_and_resource_limits(tmp_path: Path) -> None:
    sandbox = create_minimal_sandbox(REPO_ROOT, tmp_path / "run")
    executor = DockerExecutor(image=DEFAULT_MINIMAL_IMAGE, brief_root=sandbox.brief_root, project_root=sandbox.project_root)
    command = executor.build_command()
    mounts = [command[index + 1] for index, value in enumerate(command[:-1]) if value == "--mount"]

    assert "--network" in command and command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert "--cap-drop" in command and command[command.index("--cap-drop") + 1] == "ALL"
    assert "--security-opt" in command and "no-new-privileges:true" in command
    assert "--pids-limit" in command and command[command.index("--pids-limit") + 1] == "64"
    assert "--memory" in command and command[command.index("--memory") + 1] == "1g"
    assert "--cpus" in command and command[command.index("--cpus") + 1] == "2"
    assert len(mounts) == 2
    assert any("target=/workspace/brief,readonly" in mount for mount in mounts)
    assert any("target=/workspace/project" in mount and "readonly" not in mount for mount in mounts)
    assert not any("env-file" in value or "DEEPSEEK_API_KEY" in value or "OPENAI_API_KEY" in value for value in command)
    assert executor.timeout_sec == 60.0
    assert executor.output_limit_bytes == 128 * 1024


def test_real_container_isolation_and_persistent_python_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = create_minimal_runtime(REPO_ROOT, tmp_path / "run")
    host_marker = tmp_path / "host-only-marker.txt"
    host_marker.write_text("not mounted", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "runtime-isolation-test-sentinel")

    first = runtime.tools.dispatch("execute_python", {"code": "print('python-ready')"})
    assert first["status"] == "completed"
    assert first["stdout"].strip() == "python-ready"

    runtime.tools.dispatch("write_file", {"path": "project/state/value.txt", "content": "persistent"})
    runtime.tools.dispatch("write_file", {"path": "project/run_file.py", "content": "print('file-run')\n"})
    file_execution = runtime.tools.dispatch("execute_python", {"path": "project/run_file.py"})
    assert file_execution["status"] == "completed"
    assert file_execution["stdout"].strip() == "file-run"
    code = "\n".join(
        [
            "import importlib.util, os, socket",
            "from pathlib import Path",
            "assert Path('/workspace/project/state/value.txt').read_text() == 'persistent'",
            "Path('/workspace/project/python-created.txt').write_text('kept')",
            "assert not os.environ.get('DEEPSEEK_API_KEY')",
            f"assert not Path({str(host_marker)!r}).exists()",
            "assert all(importlib.util.find_spec(name) is None for name in ('numpy', 'networkx', 'shapely'))",
            "try:",
            "    Path('/workspace/brief/.write-probe').write_text('blocked')",
            "except OSError:",
            "    pass",
            "else:",
            "    raise AssertionError('brief mount is writable')",
            "try:",
            "    socket.create_connection(('192.0.2.1', 65000), timeout=1)",
            "except OSError:",
            "    print('isolation-ok')",
            "else:",
            "    raise AssertionError('container has network access')",
        ]
    )
    isolated = runtime.tools.dispatch("execute_python", {"code": code})

    assert isolated["status"] == "completed", isolated
    assert isolated["stdout"].strip() == "isolation-ok"
    assert (runtime.sandbox.project_root / "python-created.txt").read_text(encoding="utf-8") == "kept"
    assert not (runtime.sandbox.brief_root / ".write-probe").exists()
    assert runtime.tools.dispatch("finish_project", {}) == {"status": "finish_requested"}


def test_minimal_runner_is_separate_and_has_no_evaluator_dependency() -> None:
    from self_organizing_engineering_agent.experiments.ugs_synth_minimal import runner

    runtime_source = Path(runner.__file__).read_text(encoding="utf-8")

    assert runner.MAX_MODEL_TURNS == 600
    assert runner.MAX_OUTPUT_TOKENS == 65536
    assert runner.MAX_LENGTH_CONTINUATIONS == 3
    assert APPARATUS_VERSION == "2.0.2"
    assert APPARATUS_CHANGE_REASON == "Clarify explicit project-completion signalling through finish_project."
    assert all(runner._valid_run_id(f"ugs_synth_minimal_development_{value}") for value in ("001", "002", "003"))
    assert not runner._valid_run_id("../ugs_synth_minimal_development_002")
    assert "evaluation.ugs_synth" not in runtime_source
    assert "evaluate_ugs_synth" not in runtime_source
    original_system_prompt = (
        "You are working in a controlled filesystem sandbox. Only read-only brief/ and read-write project/ are visible. "
        "Python runs in a resource-limited container with no network connection. "
        "No host evaluator or hidden-case data is available during the run."
    )
    assert runner.SYSTEM_PROMPT == (
        original_system_prompt
        + "\nWhen you decide that the project is complete, call finish_project."
        + "\nA normal text response does not by itself mark the project complete."
    )
    assert runner.INITIAL_AGENT_PROMPT == (
        "Complete the engineering project described in brief/ and provide the deliverables described there. "
        "You decide how to carry out the work and when it is complete."
    )
    assert ALLOWED_TOOL_NAMES == ("list_files", "read_file", "write_file", "execute_python", "finish_project")
    assert TOOL_PARAMETER_SCHEMAS["finish_project"] == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
    assert runner.SYSTEM_PROMPT.count("brief/") == 1
    assert "planner" not in runner.SYSTEM_PROMPT.lower()
    assert "summarization" not in runner.SYSTEM_PROMPT.lower()


def test_public_tree_contains_no_legacy_checker_or_solution_files() -> None:
    public_root = REPO_ROOT / "cases" / "ugs_synth_d01" / "public"
    paths = sorted(path.relative_to(public_root).as_posix() for path in public_root.rglob("*"))
    file_paths = [name for name in paths if (public_root / name).is_file()]
    content = b"\n".join((public_root / name).read_bytes() for name in file_paths).lower()
    forbidden_fragments = (
        b"reference_d01",
        b"reference_manifest",
        b"reference design",
        b"best_known",
        b"best-known",
        b"best known lcc",
        b"best-known-feasible-lcc",
        b"ugs_synth_development_001",
        b"expected_topology",
        b"expected_equipment_count",
        b"expected_pipe_count",
        b"candidate_count",
        b"test fixture",
        b"preferred_routing_strategy",
        b"preferred equipment zone",
        b"recommended_architecture",
        b"recommended workflow",
        b"route solver parameters",
        b"search hint",
        b"required todo",
        b"required notes",
        b"required memory",
        b"optimizer_output",
        b"solution script",
        b"evaluator source",
    )

    assert not any("/schemas/" in f"/{name}" for name in file_paths)
    assert not any(fragment in content for fragment in forbidden_fragments)
    assert not any(name.endswith(".py") for name in file_paths)
    decoded = content.decode("utf-8", errors="ignore")
    secret_patterns = (
        r"(?i)\bsk-[A-Za-z0-9_-]{20,}",
        r"(?i)\bBearer\s+[A-Za-z0-9._-]{20,}",
        r"(?i)(?:DEEPSEEK|OPENAI|DASHSCOPE)_API_KEY\s*=\s*[^\s#]{16,}",
    )
    assert not any(re.search(pattern, decoded) for pattern in secret_patterns)


def test_public_world_retains_engineering_boundaries_without_output_schemas() -> None:
    public_root = REPO_ROOT / "cases" / "ugs_synth_d01" / "public"

    def read(name: str) -> dict[str, object]:
        return json.loads((public_root / name).read_text(encoding="utf-8"))

    requirements = read("project_requirements.json")
    scenarios = read("operating_scenarios.json")
    site = read("site.json")
    properties = read("gas_properties.json")
    piping = read("piping_catalog.json")
    safety = read("safety_requirements.json")
    maintenance = read("maintenance_requirements.json")
    economics = read("economic_assumptions.json")
    contract = read("final_delivery_contract.json")
    calculation_basis = (public_root / "engineering_calculation_basis.md").read_text(encoding="utf-8")

    assert requirements["primary_objective"]
    assert requirements["gas_delivery_requirements"]
    assert requirements["utility_boundaries"]
    assert scenarios["units"] and scenarios["scenarios"]
    assert site["units"] == "m" and site["external_interfaces"] and site["no_build_zones"]
    assert properties["density_formula"] and properties["compressibility_proxy"]
    assert piping["classes"] and piping["diameters"] and piping["routing_levels"]
    assert safety["minimum_separation_m"]
    assert maintenance["crane_access_buffer_m"] and "removal_path_clearance_m" not in maintenance
    assert economics["discount_rate"] and economics["project_life_years"]
    assert contract["deliverables"] and "mandatory_files" not in contract and "schema_files" not in contract
    assert "Darcy" in calculation_basis and "LCC =" in calculation_basis


@pytest.fixture(autouse=True)
def _restore_readonly_tree_for_windows_cleanup(request: pytest.FixtureRequest):
    yield
    temporary_root = getattr(request.node, "funcargs", {}).get("tmp_path")
    if isinstance(temporary_root, Path) and temporary_root.exists():
        for path in temporary_root.rglob("*"):
            try:
                path.chmod(0o700 if path.is_dir() else 0o600)
            except OSError:
                pass
