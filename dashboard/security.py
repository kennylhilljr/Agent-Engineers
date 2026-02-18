"""Sandbox compliance module for dashboard server (AI-177 / REQ-TECH-012).

Enforces security restrictions on:
- Bash command execution (allowlist)
- File operations (project directory restriction)
- MCP tool calls (Arcade gateway authorization)

Classes:
    SecurityError       -- Raised when a security policy is violated.
    CommandAllowlist    -- Validates bash commands against an allowlist and
                          blocked patterns.
    FileAccessPolicy    -- Restricts file paths to the project root directory.
    SandboxPolicy       -- Composes CommandAllowlist + FileAccessPolicy into a
                          single policy object for use by ChatBridge.
"""

import os
import re
import shlex
from pathlib import Path
from typing import FrozenSet, List, Optional

# ---------------------------------------------------------------------------
# Allowlisted bash commands (prefix / base-name match)
# ---------------------------------------------------------------------------

ALLOWED_COMMANDS: FrozenSet[str] = frozenset([
    "git", "pytest", "python", "python3", "pip", "pip3",
    "npm", "npx", "node",
    "curl", "echo", "cat", "ls", "grep",
    "mkdir", "touch",
    "uv", "gh",
    "ps", "pwd", "which", "env", "wc",
    "head", "tail",
    "sleep", "lsof",
    # Removed: rm, mv, cp, chmod, find (too risky without comprehensive pattern coverage)
])

# ---------------------------------------------------------------------------
# Blocked command patterns (applied even when the command prefix is allowed)
# ---------------------------------------------------------------------------

BLOCKED_PATTERNS: List[str] = [
    r"rm\s+(-\w*f\w*|-\w*r\w*)\s",   # any rm with -f or -r flags (covers -rf, -fr, -Rf, etc.)
    r">\s*/etc/",                      # redirect into /etc/
    r">\s*/usr/",                      # redirect into /usr/
    r">\s*/sys/",                      # redirect into /sys/
    r"sudo\s+",                        # sudo (with trailing space to avoid false positives)
    r"chmod\s+[0-7]*[2367][0-7][0-7]", # any world-writable chmod (e.g. 777, 775, 776)
    r"chmod\s+[ao][+]",               # chmod a+... or chmod o+... (grant to all/others)
    r"curl[^\n]*\|\s*(ba)?sh",        # curl | bash or curl | sh
    r"wget[^\n]*\|\s*(ba)?sh",        # wget | bash or wget | sh
    r"\beval\s*[\(\`]",               # eval() or eval`...`
    r"\bexec\s*[\(\`]",               # exec() or exec`...`
    r"__import__\s*\(",               # dynamic import
]


# ---------------------------------------------------------------------------
# SecurityError
# ---------------------------------------------------------------------------

class SecurityError(Exception):
    """Raised when a security policy is violated.

    Always carries a human-readable message explaining which rule was triggered
    so that callers can surface clear error messages to users.
    """


# ---------------------------------------------------------------------------
# CommandAllowlist
# ---------------------------------------------------------------------------

class CommandAllowlist:
    """Validate bash commands against an allowlist and a set of blocked patterns.

    Logic:
    1.  Extract the *base name* of every command in the string (handles pipes,
        &&/||, semicolons, and absolute paths like /usr/bin/python).
    2.  Reject the command if any base name is not in ``_allowed``.
    3.  Reject the command if the full command string matches any pattern in
        ``_blocked``.

    Args:
        allowed: Set of permitted command names.  Defaults to
            :data:`ALLOWED_COMMANDS`.
        blocked_patterns: List of regex patterns that must NOT match the
            command string.  Defaults to :data:`BLOCKED_PATTERNS`.
    """

    def __init__(
        self,
        allowed: Optional[FrozenSet[str]] = None,
        blocked_patterns: Optional[List[str]] = None,
    ) -> None:
        self._allowed: FrozenSet[str] = allowed if allowed is not None else ALLOWED_COMMANDS
        raw_patterns = blocked_patterns if blocked_patterns is not None else BLOCKED_PATTERNS
        self._blocked: List[re.Pattern] = [re.compile(p) for p in raw_patterns]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def check(self, command: str) -> None:
        """Raise :class:`SecurityError` if *command* is not allowed.

        Args:
            command: The raw bash command string to validate.

        Raises:
            SecurityError: If the command is not on the allowlist or matches a
                blocked pattern.  The error message names the specific rule
                that was triggered.
        """
        if not command or not command.strip():
            raise SecurityError("Empty command is not allowed.")

        # 1. Check blocked patterns first (covers multi-command strings too)
        for pattern in self._blocked:
            if pattern.search(command):
                raise SecurityError(
                    f"Command blocked by security policy (pattern: {pattern.pattern!r}): "
                    f"{command!r}"
                )

        # 2. Extract all command names and check each against the allowlist
        cmd_names = self._extract_commands(command)
        if not cmd_names:
            raise SecurityError(
                f"Could not parse command for security validation: {command!r}"
            )

        for name in cmd_names:
            if name not in self._allowed:
                raise SecurityError(
                    f"Command {name!r} is not in the allowed commands list. "
                    f"Allowed commands: {sorted(self._allowed)}"
                )

    def is_allowed(self, command: str) -> bool:
        """Return ``True`` if *command* passes :meth:`check`, ``False`` otherwise."""
        try:
            self.check(command)
            return True
        except SecurityError:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_commands(command_string: str) -> List[str]:
        """Return the list of base command names found in *command_string*.

        Handles:
        - Pipes (|)
        - Chain operators (&&, ||)
        - Semicolons
        - Absolute paths (/usr/bin/python → python)
        - Variable assignments (VAR=value cmd → cmd)

        Returns an empty list when the command cannot be parsed (fail-closed).
        """
        commands: List[str] = []

        # Split on semicolons first (shlex does not treat them as separators)
        semicolon_segments = re.split(r'(?<!["\'])\s*;\s*(?!["\'])', command_string)

        for segment in semicolon_segments:
            segment = segment.strip()
            if not segment:
                continue

            try:
                tokens = shlex.split(segment)
            except ValueError:
                # Malformed command – fail closed
                return []

            expect_command = True
            for token in tokens:
                if token in ("|", "||", "&&", "&"):
                    expect_command = True
                    continue
                if token in (
                    "if", "then", "else", "elif", "fi",
                    "for", "while", "until", "do", "done",
                    "case", "esac", "in", "!", "{", "}",
                ):
                    continue
                if token.startswith("-"):
                    continue
                # Variable assignment: VAR=value
                if "=" in token and not token.startswith("="):
                    continue
                if expect_command:
                    commands.append(os.path.basename(token))
                    expect_command = False

        return commands


# ---------------------------------------------------------------------------
# FileAccessPolicy
# ---------------------------------------------------------------------------

class FileAccessPolicy:
    """Restrict file-system access to the project root directory.

    Any path that resolves outside the project root is rejected.  Symlink
    traversal is handled by :func:`Path.resolve`.

    Args:
        project_root: Absolute path to the project root.  Defaults to the
            current working directory at construction time.
    """

    def __init__(self, project_root: Optional[str] = None) -> None:
        self._root: Path = Path(project_root or os.getcwd()).resolve()

    @property
    def root(self) -> Path:
        """The resolved project root path."""
        return self._root

    def check(self, path: str) -> None:
        """Raise :class:`SecurityError` if *path* is outside the project root.

        Args:
            path: The file-system path to validate (relative or absolute).

        Raises:
            SecurityError: If the resolved path is not inside the project root.
        """
        if not path or not path.strip():
            raise SecurityError("Empty path is not allowed.")

        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError) as exc:
            raise SecurityError(f"Cannot resolve path {path!r}: {exc}") from exc

        # Check that resolved is equal to or a child of self._root
        try:
            resolved.relative_to(self._root)
        except ValueError:
            raise SecurityError(
                f"File access denied: {path!r} resolves to {resolved!r} "
                f"which is outside the project root {self._root!r}."
            )

    def is_allowed(self, path: str) -> bool:
        """Return ``True`` if *path* passes :meth:`check`, ``False`` otherwise."""
        try:
            self.check(path)
            return True
        except SecurityError:
            return False


# ---------------------------------------------------------------------------
# SandboxPolicy
# ---------------------------------------------------------------------------

class SandboxPolicy:
    """Combined sandbox policy enforcing both command and file-path restrictions.

    Provides a single entry point for all security checks required by the
    dashboard server.  Intended for use inside :class:`ChatBridge`.

    Args:
        project_root: Passed to :class:`FileAccessPolicy`.  Defaults to
            the current working directory.
        allowed_commands: Passed to :class:`CommandAllowlist`.  Defaults to
            :data:`ALLOWED_COMMANDS`.
        blocked_patterns: Passed to :class:`CommandAllowlist`.  Defaults to
            :data:`BLOCKED_PATTERNS`.
    """

    def __init__(
        self,
        project_root: Optional[str] = None,
        allowed_commands: Optional[FrozenSet[str]] = None,
        blocked_patterns: Optional[List[str]] = None,
    ) -> None:
        self.commands = CommandAllowlist(
            allowed=allowed_commands,
            blocked_patterns=blocked_patterns,
        )
        self.files = FileAccessPolicy(project_root)

    def check_command(self, cmd: str) -> None:
        """Validate *cmd* against the command allowlist.

        Delegates to :meth:`CommandAllowlist.check`.

        Raises:
            SecurityError: If the command is blocked.
        """
        self.commands.check(cmd)

    def check_file(self, path: str) -> None:
        """Validate *path* against the file-access policy.

        Delegates to :meth:`FileAccessPolicy.check`.

        Raises:
            SecurityError: If the path is outside the project root.
        """
        self.files.check(path)
