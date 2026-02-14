"""
Windsurf (Codeium) Bridge Module
==================================

Wraps Windsurf CLI interaction to provide a unified interface for the
multi-AI orchestrator. Windsurf is an AI-powered IDE by Codeium with
its own agentic coding model (Cascade).

This bridge operates Windsurf in headless CLI mode, sending coding tasks
via file-based communication and collecting results. It can run locally
(if Windsurf CLI is installed) or inside a Docker container for isolation.

Environment Variables:
    WINDSURF_MODE: "cli" (default) or "docker"
    WINDSURF_DOCKER_IMAGE: Docker image name (default: windsurfinabox:latest)
    WINDSURF_TIMEOUT: Max seconds per task (default: 300)
    WINDSURF_WORKSPACE: Working directory for Windsurf tasks
"""

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class WindsurfMode(StrEnum):
    CLI = "cli"
    DOCKER = "docker"


@dataclass
class WindsurfMessage:
    role: str
    content: str


@dataclass
class WindsurfSession:
    mode: WindsurfMode
    workspace: str
    messages: list[WindsurfMessage] = field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(WindsurfMessage(role=role, content=content))


@dataclass
class WindsurfResponse:
    content: str
    model: str = "cascade"
    files_changed: list[str] = field(default_factory=list)
    exit_code: int = 0


class WindsurfCLIClient:
    """Runs Windsurf in local CLI/headless mode."""

    def __init__(self, timeout: int = 300) -> None:
        self.timeout = timeout
        if not self._is_windsurf_installed():
            raise ImportError(
                "Windsurf CLI not found. Install from: https://codeium.com/windsurf\n"
                "Or set WINDSURF_MODE=docker to use Docker instead."
            )

    @staticmethod
    def _is_windsurf_installed() -> bool:
        try:
            result = subprocess.run(
                ["windsurf", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def send_task(self, session: WindsurfSession, task: str) -> WindsurfResponse:
        session.add_message("user", task)
        instructions_path = Path(session.workspace) / ".windsurf-instructions.md"
        output_path = Path(session.workspace) / ".windsurf-output.txt"

        instructions_path.write_text(task, encoding="utf-8")
        output_path.unlink(missing_ok=True)

        try:
            result = subprocess.run(
                [
                    "windsurf",
                    "--headless",
                    "--folder",
                    session.workspace,
                    "--execute",
                    "Follow the instructions in .windsurf-instructions.md"
                    " and write your summary to .windsurf-output.txt",
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=session.workspace,
            )
            if output_path.exists():
                content = output_path.read_text(encoding="utf-8").strip()
            elif result.stdout.strip():
                content = result.stdout.strip()
            else:
                content = (
                    f"Windsurf completed (exit code {result.returncode}) but produced no output."
                )

            files_changed = self._detect_changed_files(session.workspace)
            session.add_message("assistant", content)
            return WindsurfResponse(
                content=content,
                exit_code=result.returncode,
                files_changed=files_changed,
            )
        except subprocess.TimeoutExpired:
            session.add_message("assistant", f"Windsurf timed out after {self.timeout}s")
            return WindsurfResponse(
                content=f"Task timed out after {self.timeout} seconds.",
                exit_code=124,
            )
        finally:
            instructions_path.unlink(missing_ok=True)

    @staticmethod
    def _detect_changed_files(workspace: str) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=workspace,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return []


class WindsurfDockerClient:
    """Runs Windsurf inside a Docker container for isolation."""

    def __init__(
        self,
        image: str = "windsurfinabox:latest",
        timeout: int = 300,
    ) -> None:
        self.image = image
        self.timeout = timeout
        if not self._is_docker_available():
            raise ImportError(
                "Docker not found or not running. Install Docker or use WINDSURF_MODE=cli."
            )

    @staticmethod
    def _is_docker_available() -> bool:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def send_task(self, session: WindsurfSession, task: str) -> WindsurfResponse:
        session.add_message("user", task)
        instructions_path = Path(session.workspace) / ".windsurf-instructions.md"
        output_path = Path(session.workspace) / ".windsurf-output.txt"

        instructions_path.write_text(task, encoding="utf-8")
        output_path.unlink(missing_ok=True)

        container_name = f"windsurf-task-{int(time.time())}"
        try:
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--name",
                    container_name,
                    "-v",
                    f"{session.workspace}:/workspace",
                    "-e",
                    "TASK_FILE=/workspace/.windsurf-instructions.md",
                    "-e",
                    "OUTPUT_FILE=/workspace/.windsurf-output.txt",
                    self.image,
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if output_path.exists():
                content = output_path.read_text(encoding="utf-8").strip()
            elif result.stdout.strip():
                content = result.stdout.strip()
            else:
                content = f"Docker container exited (code {result.returncode}) with no output."

            files_changed = WindsurfCLIClient._detect_changed_files(session.workspace)
            session.add_message("assistant", content)
            return WindsurfResponse(
                content=content,
                exit_code=result.returncode,
                files_changed=files_changed,
            )
        except subprocess.TimeoutExpired:
            subprocess.run(
                ["docker", "kill", container_name],
                capture_output=True,
                timeout=10,
            )
            session.add_message("assistant", f"Docker task timed out after {self.timeout}s")
            return WindsurfResponse(
                content=f"Task timed out after {self.timeout} seconds.",
                exit_code=124,
            )
        finally:
            instructions_path.unlink(missing_ok=True)


class WindsurfBridge:
    """Unified bridge for Windsurf access."""

    def __init__(self, mode: WindsurfMode, client) -> None:
        self.mode = mode
        self._client = client

    @classmethod
    def from_env(cls) -> "WindsurfBridge":
        mode_str = os.environ.get("WINDSURF_MODE", "cli")
        try:
            mode = WindsurfMode(mode_str.lower().strip())
        except ValueError:
            print(f"Warning: Unknown WINDSURF_MODE '{mode_str}', falling back to cli")
            mode = WindsurfMode.CLI

        timeout = int(os.environ.get("WINDSURF_TIMEOUT", "300"))

        if mode == WindsurfMode.DOCKER:
            image = os.environ.get("WINDSURF_DOCKER_IMAGE", "windsurfinabox:latest")
            client = WindsurfDockerClient(image=image, timeout=timeout)
        else:
            client = WindsurfCLIClient(timeout=timeout)

        return cls(mode=mode, client=client)

    def create_session(
        self,
        workspace: str | None = None,
        task_description: str | None = None,
    ) -> WindsurfSession:
        ws = workspace or os.environ.get("WINDSURF_WORKSPACE", "")
        if not ws:
            ws = tempfile.mkdtemp(prefix="windsurf-")
        session = WindsurfSession(mode=self.mode, workspace=ws)
        if task_description:
            session.add_message("system", task_description)
        return session

    def send_task(self, session: WindsurfSession, task: str) -> WindsurfResponse:
        return self._client.send_task(session, task)

    def get_auth_info(self) -> dict[str, str]:
        info: dict[str, str] = {"mode": self.mode.value}
        if self.mode == WindsurfMode.CLI:
            info["cli_installed"] = "yes" if WindsurfCLIClient._is_windsurf_installed() else "no"
            info["cost_note"] = "Uses local Windsurf installation."
        else:
            image = os.environ.get("WINDSURF_DOCKER_IMAGE", "windsurfinabox:latest")
            info["docker_image"] = image
            info["cost_note"] = "Runs in Docker container."
        info["timeout"] = os.environ.get("WINDSURF_TIMEOUT", "300")
        return info


def print_auth_status() -> None:
    try:
        bridge = WindsurfBridge.from_env()
        info = bridge.get_auth_info()
        print("Windsurf Status:")
        for key, value in info.items():
            print(f"  {key}: {value}")
    except (ValueError, ImportError) as e:
        print(f"Windsurf error: {e}")
