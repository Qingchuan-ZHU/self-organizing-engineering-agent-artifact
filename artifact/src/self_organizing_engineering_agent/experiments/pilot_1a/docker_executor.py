"""Verified Docker execution boundary for formal Pilot 1A Python tools."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


DEFAULT_EXECUTION_TIMEOUT_SEC = 60.0
DEFAULT_MEMORY_LIMIT = "1g"
DEFAULT_CPU_LIMIT = "2"
DEFAULT_PIDS_LIMIT = 64
DEFAULT_OUTPUT_LIMIT_BYTES = 128 * 1024
DEFAULT_TMPFS = "/tmp:rw,noexec,nosuid,size=64m"
DEFAULT_IMAGE = "self-organizing-engineering-agent/pilot-1a-formal:python312"
CONTAINER_WORKSPACE = "/workspace"
CONTAINER_BRIEF = "/workspace/brief"
CONTAINER_PROJECT = "/workspace/project"


def _safe_text(value: str, replacements: tuple[tuple[str, str], ...] = ()) -> str:
    result = value
    for source, replacement in replacements:
        if source:
            result = result.replace(source, replacement)
            result = result.replace(source.replace("\\", "/"), replacement)
    return result


def _run_command(command: list[str], *, timeout_sec: float = 15.0) -> tuple[int | None, str, str, bool]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            check=False,
            env=dict(os.environ),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return None, stdout, stderr, True
    except OSError as exc:
        return None, "", type(exc).__name__, False
    return completed.returncode, completed.stdout, completed.stderr, False


def _json_command(command: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    returncode, stdout, stderr, timed_out = _run_command(command)
    if timed_out:
        return None, "command_timeout"
    if returncode != 0:
        return None, "command_failed"
    try:
        value = json.loads(stdout.strip())
    except json.JSONDecodeError:
        return None, "invalid_command_json"
    if not isinstance(value, dict):
        return None, "invalid_command_json"
    return value, None


def probe_docker_runtime() -> dict[str, Any]:
    """Return a credential-free, bounded Docker Engine fingerprint."""

    if shutil.which("docker") is None:
        return {"available": False, "blocker": "docker_cli_unavailable"}

    version, version_error = _json_command(["docker", "version", "--format", "{{json .}}"])
    if version is None:
        return {"available": False, "blocker": "docker_engine_unavailable", "detail": version_error}
    info, info_error = _json_command(["docker", "info", "--format", "{{json .}}"])
    if info is None:
        return {"available": False, "blocker": "docker_engine_unavailable", "detail": info_error}
    returncode, context_stdout, _, context_timeout = _run_command(["docker", "context", "show"])
    if context_timeout or returncode != 0:
        return {"available": False, "blocker": "docker_context_unavailable"}
    context = context_stdout.strip()
    client = version.get("Client") if isinstance(version.get("Client"), dict) else {}
    server = version.get("Server") if isinstance(version.get("Server"), dict) else {}
    return {
        "available": True,
        "context": context,
        "client_version": client.get("Version"),
        "engine_version": server.get("Version"),
        "server_api_version": server.get("ApiVersion"),
        "backend": info.get("OperatingSystem"),
        "server_os": info.get("OSType"),
        "server_architecture": info.get("Architecture"),
        "kernel_version": info.get("KernelVersion"),
        "cpus": info.get("NCPU"),
        "memory_bytes": info.get("MemTotal"),
        "cgroup_version": info.get("CgroupVersion"),
    }


def inspect_image(image: str) -> dict[str, Any]:
    """Inspect one local image without returning its environment or paths."""

    value, error = _json_command(
        ["docker", "image", "inspect", image, "--format", "{{json .}}"]
    )
    if value is None:
        return {"available": False, "image": image, "blocker": "docker_image_unavailable", "detail": error}
    repo_digests = value.get("RepoDigests")
    if not isinstance(repo_digests, list):
        repo_digests = []
    return {
        "available": True,
        "image": image,
        "image_id": value.get("Id"),
        "repo_digests": [item for item in repo_digests if isinstance(item, str)],
    }


def probe_image_packages(image: str) -> dict[str, Any]:
    """Read Python and generic package versions from the image itself."""

    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--user",
        "1000:1000",
        "--pids-limit",
        str(DEFAULT_PIDS_LIMIT),
        "--memory",
        DEFAULT_MEMORY_LIMIT,
        "--cpus",
        DEFAULT_CPU_LIMIT,
        "--tmpfs",
        DEFAULT_TMPFS,
        image,
        "python",
        "-c",
        (
            "import importlib.metadata as m, json, platform, sys; "
            "names=('numpy','networkx','shapely'); "
            "print(json.dumps({'python': platform.python_version(), "
            "'packages': {n: m.version(n) for n in names}}))"
        ),
    ]
    returncode, stdout, _, timed_out = _run_command(command, timeout_sec=30.0)
    if timed_out or returncode != 0:
        return {"available": False, "blocker": "image_package_probe_failed"}
    try:
        value = json.loads(stdout.strip())
    except json.JSONDecodeError:
        return {"available": False, "blocker": "image_package_probe_invalid"}
    if not isinstance(value, dict):
        return {"available": False, "blocker": "image_package_probe_invalid"}
    return {"available": True, **value}


class _CappedReader(threading.Thread):
    def __init__(self, stream: Any, limit_bytes: int) -> None:
        super().__init__(daemon=True)
        self.stream = stream
        self.limit_bytes = limit_bytes
        self.data = bytearray()
        self.truncated = False

    def run(self) -> None:
        while True:
            chunk = self.stream.read(64 * 1024)
            if not chunk:
                return
            remaining = self.limit_bytes - len(self.data)
            if remaining > 0:
                self.data.extend(chunk[:remaining])
            if len(chunk) > max(0, remaining):
                self.truncated = True


class DockerExecutor:
    """Run Agent Python with exactly the formal container policy."""

    def __init__(
        self,
        *,
        image: str,
        brief_root: Path,
        project_root: Path,
        timeout_sec: float = DEFAULT_EXECUTION_TIMEOUT_SEC,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: str = DEFAULT_CPU_LIMIT,
        pids_limit: int = DEFAULT_PIDS_LIMIT,
        output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES,
    ) -> None:
        self.image = image
        self.brief_root = brief_root.resolve()
        self.project_root = project_root.resolve()
        self.timeout_sec = timeout_sec
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.pids_limit = pids_limit
        self.output_limit_bytes = output_limit_bytes

    def _container_project_path(self, project_path: Path) -> str:
        resolved = project_path.resolve(strict=True)
        try:
            relative = resolved.relative_to(self.project_root)
        except ValueError as exc:
            raise ValueError("project path leaves the mounted project") from exc
        return (Path(CONTAINER_PROJECT) / relative).as_posix()

    def build_command(self, *, project_path: Path | None = None) -> list[str]:
        command = [
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--user",
            "1000:1000",
            "--pids-limit",
            str(self.pids_limit),
            "--memory",
            self.memory_limit,
            "--cpus",
            self.cpu_limit,
            "--tmpfs",
            DEFAULT_TMPFS,
            "--workdir",
            CONTAINER_WORKSPACE,
            "--mount",
            f"type=bind,source={self.brief_root},target={CONTAINER_BRIEF},readonly",
            "--mount",
            f"type=bind,source={self.project_root},target={CONTAINER_PROJECT}",
            "--env",
            "PYTHONUNBUFFERED=1",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            self.image,
            "python",
        ]
        if project_path is None:
            command.append("-")
        else:
            command.append(self._container_project_path(project_path))
        return command

    def execute(self, *, code: str | None = None, project_path: Path | None = None) -> dict[str, Any]:
        if (code is None) == (project_path is None):
            raise ValueError("exactly one of code or project_path is required")
        command = self.build_command(project_path=project_path)
        started = time.perf_counter()
        replacements = (
            (str(self.brief_root), "<brief>"),
            (str(self.project_root), "<project>"),
        )
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # These variables are visible only to the host-side Docker CLI;
                # the container receives the two explicit --env entries above.
                env=dict(os.environ),
            )
        except OSError as exc:
            return {
                "status": "container_runtime_unavailable",
                "exit_code": None,
                "stdout": "",
                "stderr": type(exc).__name__,
                "stdout_truncated": False,
                "stderr_truncated": False,
                "duration_sec": round(time.perf_counter() - started, 6),
                "timeout": False,
            }

        stdout_reader = _CappedReader(process.stdout, self.output_limit_bytes)
        stderr_reader = _CappedReader(process.stderr, self.output_limit_bytes)
        stdout_reader.start()
        stderr_reader.start()

        def write_stdin() -> None:
            if process.stdin is None:
                return
            try:
                if code is not None:
                    process.stdin.write(code.encode("utf-8"))
                process.stdin.close()
            except (BrokenPipeError, OSError):
                try:
                    process.stdin.close()
                except OSError:
                    pass

        writer = threading.Thread(target=write_stdin, daemon=True)
        writer.start()
        timed_out = False
        try:
            exit_code = process.wait(timeout=self.timeout_sec)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            exit_code = process.wait(timeout=10.0)
        writer.join(timeout=5.0)
        stdout_reader.join(timeout=5.0)
        stderr_reader.join(timeout=5.0)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        stdout = _safe_text(stdout_reader.data.decode("utf-8", "replace"), replacements)
        stderr = _safe_text(stderr_reader.data.decode("utf-8", "replace"), replacements)
        return {
            "status": "execution_timeout" if timed_out else ("completed" if exit_code == 0 else "execution_error"),
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_reader.truncated,
            "stderr_truncated": stderr_reader.truncated,
            "duration_sec": round(time.perf_counter() - started, 6),
            "timeout": timed_out,
        }
