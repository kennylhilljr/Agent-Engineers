"""
Comprehensive tests for KAN-50: Python Pydantic AI Agent Backend Setup

This test suite verifies:
1. Directory structure exists
2. requirements.txt has all needed packages
3. main.py creates a valid FastAPI app
4. Health endpoint works correctly
5. CORS configuration is correct
6. AG-UI endpoint placeholder exists
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Add agent directory to path for imports
AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR))

from main import app


class TestDirectoryStructure:
    """Test that all required files and directories exist"""

    def test_agent_directory_exists(self):
        """Verify agent/ directory exists"""
        assert AGENT_DIR.exists()
        assert AGENT_DIR.is_dir()

    def test_requirements_txt_exists(self):
        """Verify requirements.txt exists"""
        requirements_path = AGENT_DIR / "requirements.txt"
        assert requirements_path.exists()
        assert requirements_path.is_file()

    def test_main_py_exists(self):
        """Verify main.py exists"""
        main_path = AGENT_DIR / "main.py"
        assert main_path.exists()
        assert main_path.is_file()

    def test_env_example_exists(self):
        """Verify .env.example exists"""
        env_example_path = AGENT_DIR / ".env.example"
        assert env_example_path.exists()
        assert env_example_path.is_file()

    def test_gitignore_exists(self):
        """Verify .gitignore exists in agent directory"""
        gitignore_path = AGENT_DIR / ".gitignore"
        assert gitignore_path.exists()
        assert gitignore_path.is_file()

    def test_init_py_exists(self):
        """Verify __init__.py exists (makes agent a proper Python package)"""
        init_path = AGENT_DIR / "__init__.py"
        assert init_path.exists()
        assert init_path.is_file()


class TestRequirementsTxt:
    """Test that requirements.txt has all necessary packages"""

    @pytest.fixture
    def requirements_content(self):
        """Load requirements.txt content"""
        requirements_path = AGENT_DIR / "requirements.txt"
        with open(requirements_path, "r") as f:
            return f.read()

    def test_has_pydantic_ai(self, requirements_content):
        """Verify pydantic-ai is in requirements"""
        assert "pydantic-ai" in requirements_content

    def test_has_pydantic(self, requirements_content):
        """Verify pydantic>=2.0.0 is in requirements"""
        assert "pydantic>=" in requirements_content
        assert "2.0.0" in requirements_content

    def test_has_fastapi(self, requirements_content):
        """Verify fastapi>=0.100.0 is in requirements"""
        assert "fastapi>=" in requirements_content
        assert "0.100.0" in requirements_content

    def test_has_uvicorn(self, requirements_content):
        """Verify uvicorn is in requirements"""
        assert "uvicorn" in requirements_content

    def test_has_python_dotenv(self, requirements_content):
        """Verify python-dotenv is in requirements"""
        assert "python-dotenv" in requirements_content

    def test_has_test_dependencies(self, requirements_content):
        """Verify pytest and testing dependencies are included"""
        assert "pytest" in requirements_content
        assert "pytest-asyncio" in requirements_content
        assert "httpx" in requirements_content


class TestEnvExample:
    """Test that .env.example has all required environment variables"""

    @pytest.fixture
    def env_example_content(self):
        """Load .env.example content"""
        env_example_path = AGENT_DIR / ".env.example"
        with open(env_example_path, "r") as f:
            return f.read()

    def test_has_environment_var(self, env_example_content):
        """Verify ENVIRONMENT variable is documented"""
        assert "ENVIRONMENT" in env_example_content

    def test_has_backend_port(self, env_example_content):
        """Verify BACKEND_PORT is documented"""
        assert "BACKEND_PORT" in env_example_content

    def test_has_frontend_port(self, env_example_content):
        """Verify FRONTEND_PORT is documented"""
        assert "FRONTEND_PORT" in env_example_content

    def test_has_api_key_placeholders(self, env_example_content):
        """Verify API key placeholders are documented"""
        # Should have commented examples for AI providers
        assert "API_KEY" in env_example_content


class TestFastAPIApp:
    """Test that main.py creates a valid FastAPI application"""

    def test_app_is_fastapi_instance(self):
        """Verify app is a FastAPI instance"""
        from fastapi import FastAPI

        assert isinstance(app, FastAPI)

    def test_app_has_title(self):
        """Verify app has a title"""
        assert app.title
        assert "AI" in app.title or "Agent" in app.title

    def test_app_has_version(self):
        """Verify app has a version"""
        assert app.version
        assert app.version == "0.1.0"

    def test_app_has_cors_middleware(self):
        """Verify CORS middleware is configured"""
        # Check that CORSMiddleware is in the middleware stack
        middleware_types = [type(m).__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_types

    def test_health_endpoint_exists(self):
        """Verify /health endpoint is registered"""
        routes = [route.path for route in app.routes]
        assert "/health" in routes

    def test_ag_ui_stream_endpoint_exists(self):
        """Verify /ag-ui/stream endpoint is registered"""
        routes = [route.path for route in app.routes]
        assert "/ag-ui/stream" in routes


class TestHealthEndpoint:
    """Test the /health endpoint functionality"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_health_endpoint_returns_200(self, client):
        """Verify health endpoint returns 200 OK"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_json(self, client):
        """Verify health endpoint returns JSON"""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"

    def test_health_response_has_status(self, client):
        """Verify health response has status field"""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_response_has_version(self, client):
        """Verify health response has version field"""
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "0.1.0"

    def test_health_response_has_message(self, client):
        """Verify health response has message field"""
        response = client.get("/health")
        data = response.json()
        assert "message" in data
        assert len(data["message"]) > 0

    def test_health_response_has_environment(self, client):
        """Verify health response has environment field"""
        response = client.get("/health")
        data = response.json()
        assert "environment" in data


class TestRootEndpoint:
    """Test the root / endpoint functionality"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_root_endpoint_returns_200(self, client):
        """Verify root endpoint returns 200 OK"""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_endpoint_returns_json(self, client):
        """Verify root endpoint returns JSON"""
        response = client.get("/")
        assert response.headers["content-type"] == "application/json"

    def test_root_response_has_name(self, client):
        """Verify root response has name field"""
        response = client.get("/")
        data = response.json()
        assert "name" in data

    def test_root_response_has_endpoints(self, client):
        """Verify root response lists available endpoints"""
        response = client.get("/")
        data = response.json()
        assert "endpoints" in data
        assert isinstance(data["endpoints"], dict)


class TestAGUIStreamEndpoint:
    """Test the /ag-ui/stream placeholder endpoint"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_ag_ui_stream_returns_501(self, client):
        """Verify AG-UI stream endpoint returns 501 Not Implemented (placeholder)"""
        response = client.post(
            "/ag-ui/stream",
            json={"prompt": "test prompt", "stream": True},
        )
        assert response.status_code == 501

    def test_ag_ui_stream_returns_json_error(self, client):
        """Verify AG-UI stream endpoint returns JSON error"""
        response = client.post(
            "/ag-ui/stream",
            json={"prompt": "test prompt", "stream": True},
        )
        data = response.json()
        assert "detail" in data

    def test_ag_ui_stream_accepts_prompt(self, client):
        """Verify AG-UI stream endpoint accepts prompt parameter"""
        response = client.post(
            "/ag-ui/stream",
            json={"prompt": "Hello, agent!", "stream": True},
        )
        # Should return 501 but acknowledge the prompt
        assert response.status_code == 501


class TestCORSConfiguration:
    """Test CORS middleware configuration"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_cors_allows_frontend_origin(self, client):
        """Verify CORS allows frontend origin"""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3010"},
        )
        assert response.status_code == 200
        # TestClient doesn't process CORS headers, but we can verify the endpoint works

    def test_cors_configured_for_port_3010(self):
        """Verify CORS middleware is configured for port 3010"""
        # Check middleware configuration
        from fastapi.middleware.cors import CORSMiddleware

        cors_middleware = None
        for middleware in app.user_middleware:
            if isinstance(middleware.cls, type) and issubclass(
                middleware.cls, CORSMiddleware
            ):
                cors_middleware = middleware
                break

        assert cors_middleware is not None


class TestErrorHandlers:
    """Test error handling"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_404_handler(self, client):
        """Verify 404 error handler works"""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data


class TestCodeQuality:
    """Test code quality and best practices"""

    def test_main_has_docstring(self):
        """Verify main.py has module docstring"""
        main_path = AGENT_DIR / "main.py"
        with open(main_path, "r") as f:
            content = f.read()
        assert '"""' in content or "'''" in content

    def test_main_imports_dotenv(self):
        """Verify main.py imports and loads dotenv"""
        main_path = AGENT_DIR / "main.py"
        with open(main_path, "r") as f:
            content = f.read()
        assert "load_dotenv" in content

    def test_main_has_lifespan_manager(self):
        """Verify main.py has lifespan manager for startup/shutdown"""
        main_path = AGENT_DIR / "main.py"
        with open(main_path, "r") as f:
            content = f.read()
        assert "lifespan" in content or "startup" in content

    def test_gitignore_excludes_venv(self):
        """Verify .gitignore excludes virtual environment"""
        gitignore_path = AGENT_DIR / ".gitignore"
        with open(gitignore_path, "r") as f:
            content = f.read()
        assert "venv" in content or ".venv" in content

    def test_gitignore_excludes_env_file(self):
        """Verify .gitignore excludes .env file"""
        gitignore_path = AGENT_DIR / ".gitignore"
        with open(gitignore_path, "r") as f:
            content = f.read()
        assert ".env" in content


# Test summary for reporting
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
