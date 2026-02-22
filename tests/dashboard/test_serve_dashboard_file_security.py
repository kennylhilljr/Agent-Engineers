"""Security tests for serve_dashboard_file endpoint (AI-262).

Tests security hardening for path traversal and file type validation:
- Path traversal attempts must return 403 or 404
- Disallowed file extensions must return 403
- Valid files with allowed extensions must return 200
- Directory containment validation must work correctly

Coverage Requirements:
- Test path traversal with ../ patterns
- Test absolute path attempts
- Test disallowed file extensions (.py, .env, .txt)
- Test allowed file extensions (.html, .js, .css, .json)
- Test symlink attacks (if applicable)
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web

from dashboard.server import DashboardServer


class TestServeDashboardFileSecurity(AioHTTPTestCase):
    """Security tests for serve_dashboard_file endpoint."""

    async def get_application(self):
        """Create test application with temporary metrics directory."""
        # Create temporary directory for test metrics
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_file = Path(self.temp_dir) / ".agent_metrics.json"

        # Create minimal metrics file
        self.metrics_file.write_text('{"project_name": "test", "agents": {}}')

        # Create test server using metrics_dir parameter
        self.server = DashboardServer(
            metrics_dir=Path(self.temp_dir),
            port=8080,
            project_name="test-project"
        )

        # Create test files in dashboard directory
        dashboard_dir = Path(__file__).parent.parent.parent / "dashboard"
        self.test_html_file = dashboard_dir / "test_security.html"
        self.test_js_file = dashboard_dir / "test_security.js"
        self.test_py_file = dashboard_dir / "test_security.py"

        # Create test files
        self.test_html_file.write_text('<html><body>Test</body></html>')
        self.test_js_file.write_text('console.log("test");')
        self.test_py_file.write_text('print("test")')

        return self.server.app

    async def tearDownAsync(self):
        """Clean up test files."""
        # Remove test files
        for f in [self.test_html_file, self.test_js_file, self.test_py_file]:
            if f.exists():
                f.unlink()

        # Clean up temporary directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    # =========================================================================
    # Path Traversal Tests
    # =========================================================================

    async def test_path_traversal_double_dot(self):
        """Test that ../ path traversal is blocked."""
        resp = await self.client.get('/dashboard/../server.py')
        assert resp.status in [403, 404], "Path traversal with ../ should be blocked"

    async def test_path_traversal_etc_passwd(self):
        """Test that attempts to access /etc/passwd are blocked."""
        resp = await self.client.get('/dashboard/../../etc/passwd')
        assert resp.status in [403, 404], "Path traversal to /etc/passwd should be blocked"

    async def test_path_traversal_multiple_levels(self):
        """Test that multiple ../ levels are blocked."""
        resp = await self.client.get('/dashboard/../../../etc/passwd')
        assert resp.status in [403, 404], "Multiple level path traversal should be blocked"

    async def test_path_traversal_url_encoded(self):
        """Test that URL-encoded path traversal is blocked."""
        resp = await self.client.get('/dashboard/..%2F..%2Fetc%2Fpasswd')
        assert resp.status in [403, 404], "URL-encoded path traversal should be blocked"

    async def test_absolute_path_attempt(self):
        """Test that absolute paths starting with / are blocked."""
        resp = await self.client.get('/dashboard//etc/passwd')
        assert resp.status in [403, 404], "Absolute path should be blocked"

    async def test_windows_path_traversal(self):
        """Test that Windows-style path traversal with backslashes is blocked."""
        resp = await self.client.get('/dashboard/..\\..\\etc\\passwd')
        assert resp.status in [403, 404], "Windows-style path traversal should be blocked"

    async def test_mixed_slashes(self):
        """Test that mixed forward and back slashes are blocked."""
        resp = await self.client.get('/dashboard/../\\../etc/passwd')
        assert resp.status in [403, 404], "Mixed slash path traversal should be blocked"

    # =========================================================================
    # File Extension Validation Tests
    # =========================================================================

    async def test_allowed_extension_html(self):
        """Test that .html files are allowed."""
        resp = await self.client.get('/dashboard/test_security.html')
        assert resp.status == 200, ".html files should be allowed"
        assert resp.content_type == 'text/html'

    async def test_allowed_extension_js(self):
        """Test that .js files are allowed."""
        resp = await self.client.get('/dashboard/test_security.js')
        assert resp.status == 200, ".js files should be allowed"
        assert resp.content_type == 'application/javascript'

    async def test_disallowed_extension_py(self):
        """Test that .py files are blocked."""
        resp = await self.client.get('/dashboard/test_security.py')
        assert resp.status == 403, ".py files should be blocked"

    async def test_disallowed_extension_env(self):
        """Test that .env files are blocked."""
        resp = await self.client.get('/dashboard/.env')
        assert resp.status in [403, 404], ".env files should be blocked"

    async def test_disallowed_extension_txt(self):
        """Test that .txt files are blocked."""
        resp = await self.client.get('/dashboard/test.txt')
        assert resp.status in [403, 404], ".txt files should be blocked"

    async def test_disallowed_extension_sh(self):
        """Test that .sh files are blocked."""
        resp = await self.client.get('/dashboard/test.sh')
        assert resp.status in [403, 404], ".sh files should be blocked"

    async def test_disallowed_extension_yaml(self):
        """Test that .yaml files are blocked."""
        resp = await self.client.get('/dashboard/config.yaml')
        assert resp.status in [403, 404], ".yaml files should be blocked"

    async def test_disallowed_extension_yml(self):
        """Test that .yml files are blocked."""
        resp = await self.client.get('/dashboard/config.yml')
        assert resp.status in [403, 404], ".yml files should be blocked"

    async def test_disallowed_extension_json_backup(self):
        """Test that non-standard extensions are blocked."""
        resp = await self.client.get('/dashboard/backup.json.bak')
        assert resp.status in [403, 404], ".json.bak files should be blocked"

    async def test_no_extension(self):
        """Test that files without extension are blocked."""
        resp = await self.client.get('/dashboard/README')
        assert resp.status in [403, 404], "Files without extension should be blocked"

    # =========================================================================
    # Case Sensitivity Tests
    # =========================================================================

    async def test_case_insensitive_extension_html(self):
        """Test that .HTML (uppercase) is treated as allowed."""
        dashboard_dir = Path(__file__).parent.parent.parent / "dashboard"
        test_file = dashboard_dir / "test_case.HTML"
        test_file.write_text('<html>Test</html>')

        try:
            resp = await self.client.get('/dashboard/test_case.HTML')
            # Should either work (200) or not be found (404), but NOT be forbidden (403)
            # because .HTML should be normalized to .html
            assert resp.status in [200, 404], ".HTML should be normalized to .html"
        finally:
            if test_file.exists():
                test_file.unlink()

    # =========================================================================
    # Directory Containment Tests
    # =========================================================================

    async def test_directory_containment_symlink(self):
        """Test that symlinks pointing outside dashboard dir are blocked."""
        # This test may be skipped on systems that don't support symlinks
        dashboard_dir = Path(__file__).parent.parent.parent / "dashboard"
        symlink_path = dashboard_dir / "test_symlink.html"

        try:
            # Create symlink pointing to /etc/passwd
            if os.name != 'nt':  # Skip on Windows
                os.symlink('/etc/passwd', symlink_path)

                resp = await self.client.get('/dashboard/test_symlink.html')
                # Should be blocked because resolved path is outside dashboard dir
                assert resp.status in [403, 404], "Symlink to outside directory should be blocked"
        except OSError:
            pytest.skip("Symlinks not supported on this system")
        finally:
            if symlink_path.exists() or symlink_path.is_symlink():
                symlink_path.unlink()

    async def test_file_not_found(self):
        """Test that non-existent files return 404."""
        resp = await self.client.get('/dashboard/nonexistent.html')
        assert resp.status == 404, "Non-existent file should return 404"

    # =========================================================================
    # Valid Access Tests
    # =========================================================================

    async def test_valid_html_file_access(self):
        """Test that valid .html files can be accessed."""
        resp = await self.client.get('/dashboard/test_security.html')
        assert resp.status == 200
        assert resp.content_type == 'text/html'
        content = await resp.text()
        assert '<html>' in content

    async def test_valid_js_file_access(self):
        """Test that valid .js files can be accessed."""
        resp = await self.client.get('/dashboard/test_security.js')
        assert resp.status == 200
        assert resp.content_type == 'application/javascript'
        content = await resp.text()
        assert 'console.log' in content

    # =========================================================================
    # Edge Cases
    # =========================================================================

    async def test_empty_filename(self):
        """Test that empty filename is blocked."""
        resp = await self.client.get('/dashboard/')
        assert resp.status in [403, 404], "Empty filename should be blocked"

    async def test_dot_file(self):
        """Test that dot files without extension are blocked."""
        resp = await self.client.get('/dashboard/.hidden')
        assert resp.status in [403, 404], "Dot files should be blocked"

    async def test_null_byte_injection(self):
        """Test that null byte injection is handled safely."""
        # URL encoding for null byte is %00
        resp = await self.client.get('/dashboard/test.html%00.py')
        # Framework handles this at a lower level - may return 500, 404, or 403
        # The important thing is it doesn't serve the .py file
        assert resp.status in [403, 404, 500], "Null byte injection should be blocked or error"


# =========================================================================
# Standalone Test Functions
# =========================================================================

def test_allowed_extensions_whitelist():
    """Verify the allowed extensions whitelist is correct."""
    # This is a code inspection test - we verify the whitelist in code
    # The actual whitelist is defined in the serve_dashboard_file method
    expected_extensions = {'.html', '.js', '.css', '.json'}

    # Read the server.py file and check for the whitelist
    server_file = Path(__file__).parent.parent.parent / "dashboard" / "server.py"
    content = server_file.read_text()

    # Verify ALLOWED_EXTENSIONS exists and contains the right elements
    assert "ALLOWED_EXTENSIONS = {" in content, "ALLOWED_EXTENSIONS must be defined"

    # Check all expected extensions are present
    for ext in expected_extensions:
        assert f"'{ext}'" in content or f'"{ext}"' in content, \
               f"ALLOWED_EXTENSIONS must contain {ext}"


def test_path_relative_to_check():
    """Verify that path.relative_to() is used for directory containment."""
    server_file = Path(__file__).parent.parent.parent / "dashboard" / "server.py"
    content = server_file.read_text()

    # Verify the security pattern is present
    assert "file_path.relative_to(dashboard_dir)" in content, \
           "Must use path.relative_to() for directory containment validation"

    assert "except ValueError:" in content, \
           "Must catch ValueError from relative_to() for paths outside directory"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
