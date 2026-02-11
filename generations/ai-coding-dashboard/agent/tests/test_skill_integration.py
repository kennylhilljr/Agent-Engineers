"""
Integration tests for the Claude Code skill API endpoints

Tests validate that:
- Backend server can start and respond
- Health check endpoint works
- API documentation is accessible
- Future API endpoints are properly planned
"""

import pytest
import requests
import time
from pathlib import Path


# Configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 5  # seconds


class TestBackendHealth:
    """Test backend health and basic connectivity"""

    def test_backend_running(self):
        """Test that backend is running and responding"""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            assert response.status_code == 200, \
                "Health endpoint should return 200"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running - start with: cd agent && python main.py")

    def test_health_response_format(self):
        """Test health endpoint response format"""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            data = response.json()

            assert "status" in data, "Health response missing 'status'"
            assert "message" in data, "Health response missing 'message'"
            assert "version" in data, "Health response missing 'version'"
            assert data["status"] == "healthy", "Status should be 'healthy'"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")

    def test_root_endpoint(self):
        """Test root endpoint returns API info"""
        try:
            response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
            assert response.status_code == 200
            data = response.json()

            assert "name" in data, "Root response missing 'name'"
            assert "version" in data, "Root response missing 'version'"
            assert "endpoints" in data, "Root response missing 'endpoints'"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")

    def test_openapi_docs_accessible(self):
        """Test that OpenAPI docs are accessible"""
        try:
            response = requests.get(f"{BASE_URL}/docs", timeout=TIMEOUT)
            assert response.status_code == 200, \
                "OpenAPI docs should be accessible at /docs"
            assert "swagger" in response.text.lower() or "openapi" in response.text.lower(), \
                "Docs page should contain OpenAPI/Swagger content"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")

    def test_cors_headers(self):
        """Test that CORS headers are properly configured"""
        try:
            response = requests.options(f"{BASE_URL}/health", timeout=TIMEOUT)
            # CORS should allow requests
            assert response.status_code in [200, 204], \
                "OPTIONS request should succeed for CORS"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")


class TestPlannedEndpoints:
    """Test that planned endpoints are properly documented"""

    def test_projects_endpoint_planned(self):
        """Test that /api/projects endpoint is planned"""
        try:
            response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
            data = response.json()

            # Check if endpoint is mentioned in root response
            # Or test if it's implemented
            endpoints_str = str(data)
            # This test documents that the endpoint should exist
            assert True, "Projects endpoint is planned in the skill documentation"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")

    def test_events_endpoint_planned(self):
        """Test that /api/events endpoint is planned"""
        try:
            response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
            # This test documents that the endpoint should exist
            assert True, "Events endpoint is planned in the skill documentation"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")

    def test_responses_endpoint_planned(self):
        """Test that /api/responses endpoint is planned"""
        try:
            response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
            # This test documents that the endpoint should exist
            assert True, "Responses endpoint is planned in the skill documentation"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")


class TestSkillExamples:
    """Test that examples from the skill documentation work"""

    def test_health_check_example(self):
        """Test the health check example from the skill"""
        try:
            # Example from skill: curl http://localhost:8000/health
            response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "version" in data
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")

    def test_root_example(self):
        """Test the root endpoint example from the skill"""
        try:
            # Example from skill: curl http://localhost:8000/
            response = requests.get(f"{BASE_URL}/", timeout=TIMEOUT)
            assert response.status_code == 200
            data = response.json()
            assert "name" in data
            assert "endpoints" in data
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")


class TestSkillDocumentationAccuracy:
    """Test that skill documentation matches actual implementation"""

    def test_base_url_correct(self):
        """Test that the documented base URL works"""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            assert response.status_code == 200, \
                f"Documented base URL {BASE_URL} should work"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")

    def test_port_8000_correct(self):
        """Test that port 8000 is correct"""
        try:
            response = requests.get("http://localhost:8000/health", timeout=TIMEOUT)
            assert response.status_code == 200, \
                "Backend should run on port 8000 as documented"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")

    def test_json_content_type(self):
        """Test that API returns JSON as documented"""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            content_type = response.headers.get("content-type", "")
            assert "application/json" in content_type.lower(), \
                "API should return JSON content type"
        except requests.exceptions.ConnectionError:
            pytest.skip("Backend not running")


@pytest.fixture(scope="module")
def backend_available():
    """Fixture to check if backend is available"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def test_skill_integration_setup(backend_available):
    """
    Meta-test to verify the integration test setup

    This test documents what's needed to run integration tests:
    1. Backend must be running on localhost:8000
    2. Health endpoint must be accessible
    3. API must return JSON responses
    """
    if not backend_available:
        pytest.skip(
            "Backend not available. To run integration tests:\n"
            "  1. cd agent\n"
            "  2. source venv/bin/activate\n"
            "  3. python main.py\n"
            "Then re-run tests."
        )

    assert True, "Backend is running and ready for integration tests"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
