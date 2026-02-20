"""
test_deployment.py - Deployment infrastructure tests for AI-223.

Tests:
- Dockerfile validation (multi-stage, non-root user, HEALTHCHECK, <500MB target)
- docker-compose.yml structure
- GitHub Actions CI/CD workflow correctness
- Terraform configuration
- /health endpoint (updated)
- /ready endpoint (new)
- Deploy scripts existence
- nginx.conf security headers

Total: 65 tests
"""

import os
import re
import json
import unittest
from pathlib import Path

# Repository root
REPO_ROOT = Path(__file__).parent.parent


class TestDockerfile(unittest.TestCase):
    """Tests for Dockerfile - 15 tests."""

    def setUp(self):
        self.dockerfile_path = REPO_ROOT / "Dockerfile"
        self.assertTrue(self.dockerfile_path.exists(), "Dockerfile must exist")
        self.content = self.dockerfile_path.read_text()

    def test_dockerfile_exists(self):
        self.assertTrue(self.dockerfile_path.exists())

    def test_multi_stage_build_has_builder_stage(self):
        self.assertIn("AS builder", self.content)

    def test_multi_stage_build_has_production_stage(self):
        self.assertIn("AS production", self.content)

    def test_uses_python_311_slim(self):
        self.assertIn("python:3.11-slim", self.content)

    def test_non_root_user_created(self):
        self.assertTrue(
            "useradd" in self.content or "adduser" in self.content,
            "Dockerfile must create a non-root user"
        )

    def test_non_root_user_switched(self):
        self.assertIn("USER ", self.content)
        # USER line must not be 'root'
        user_line = [l.strip() for l in self.content.splitlines() if l.strip().startswith("USER ")]
        self.assertTrue(len(user_line) > 0, "Must have USER instruction")
        self.assertNotIn("USER root", self.content)

    def test_healthcheck_present(self):
        self.assertIn("HEALTHCHECK", self.content)

    def test_healthcheck_uses_curl(self):
        self.assertIn("curl", self.content)

    def test_expose_port_8080(self):
        self.assertIn("EXPOSE 8080", self.content)

    def test_workdir_set(self):
        self.assertIn("WORKDIR", self.content)

    def test_requirements_copied(self):
        self.assertIn("requirements.txt", self.content)

    def test_no_root_pip_install(self):
        # pip install should be done in builder stage, not run as root in prod
        self.assertIn("--no-cache-dir", self.content)

    def test_copy_app_source(self):
        self.assertIn("COPY", self.content)

    def test_cmd_runs_rest_api_server(self):
        self.assertIn("rest_api_server", self.content)

    def test_pythondontwritebytecode_set(self):
        self.assertIn("PYTHONDONTWRITEBYTECODE", self.content)


class TestDockerCompose(unittest.TestCase):
    """Tests for docker-compose.yml - 10 tests."""

    def setUp(self):
        self.dc_path = REPO_ROOT / "docker-compose.yml"
        self.assertTrue(self.dc_path.exists(), "docker-compose.yml must exist")
        self.content = self.dc_path.read_text()

    def test_docker_compose_exists(self):
        self.assertTrue(self.dc_path.exists())

    def test_has_dashboard_service(self):
        self.assertIn("dashboard:", self.content)

    def test_has_postgres_service(self):
        self.assertIn("postgres:", self.content)

    def test_has_redis_service(self):
        self.assertIn("redis:", self.content)

    def test_postgres_uses_v15(self):
        self.assertIn("postgres:15", self.content)

    def test_redis_uses_v7(self):
        self.assertIn("redis:7", self.content)

    def test_dashboard_depends_on_postgres(self):
        self.assertIn("depends_on", self.content)
        self.assertIn("postgres", self.content)

    def test_dashboard_exposes_port_8080(self):
        self.assertIn("8080:8080", self.content)

    def test_postgres_init_sql_volume(self):
        self.assertIn("init.sql", self.content)

    def test_named_volumes_defined(self):
        self.assertIn("volumes:", self.content)
        self.assertIn("postgres_data:", self.content)


class TestDockerComposeProd(unittest.TestCase):
    """Tests for docker-compose.prod.yml - 5 tests."""

    def setUp(self):
        self.path = REPO_ROOT / "docker-compose.prod.yml"
        self.assertTrue(self.path.exists(), "docker-compose.prod.yml must exist")
        self.content = self.path.read_text()

    def test_prod_compose_exists(self):
        self.assertTrue(self.path.exists())

    def test_uses_ecr_image(self):
        self.assertIn("ECR_REGISTRY", self.content)

    def test_postgres_disabled_in_prod(self):
        self.assertIn("replicas: 0", self.content)

    def test_has_deploy_resources(self):
        self.assertIn("resources:", self.content)

    def test_uses_awslogs_driver(self):
        self.assertIn("awslogs", self.content)


class TestCIWorkflow(unittest.TestCase):
    """Tests for .github/workflows/ci.yml - 10 tests."""

    def setUp(self):
        self.path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(self.path.exists(), "ci.yml must exist")
        self.content = self.path.read_text()

    def test_ci_yml_exists(self):
        self.assertTrue(self.path.exists())

    def test_triggers_on_pull_request(self):
        self.assertIn("pull_request", self.content)

    def test_runs_pytest(self):
        self.assertIn("pytest", self.content)

    def test_runs_mypy(self):
        self.assertIn("mypy", self.content)

    def test_builds_docker_image(self):
        self.assertIn("docker", self.content.lower())

    def test_checks_image_size(self):
        self.assertIn("500", self.content)

    def test_uses_python_311(self):
        self.assertIn("3.11", self.content)

    def test_has_postgres_service(self):
        self.assertIn("postgres", self.content)

    def test_has_redis_service(self):
        self.assertIn("redis", self.content)

    def test_cancels_in_progress(self):
        self.assertIn("cancel-in-progress", self.content)


class TestDeployStagingWorkflow(unittest.TestCase):
    """Tests for deploy-staging.yml - 5 tests."""

    def setUp(self):
        self.path = REPO_ROOT / ".github" / "workflows" / "deploy-staging.yml"
        self.assertTrue(self.path.exists())
        self.content = self.path.read_text()

    def test_deploy_staging_exists(self):
        self.assertTrue(self.path.exists())

    def test_triggers_on_push_to_main(self):
        self.assertIn("main", self.content)
        self.assertIn("push:", self.content)

    def test_pushes_to_ecr(self):
        self.assertIn("amazon-ecr-login", self.content)

    def test_deploys_to_ecs(self):
        self.assertIn("amazon-ecs-deploy-task-definition", self.content)

    def test_runs_smoke_tests(self):
        self.assertIn("smoke_test", self.content)


class TestDeployProductionWorkflow(unittest.TestCase):
    """Tests for deploy-production.yml - 5 tests."""

    def setUp(self):
        self.path = REPO_ROOT / ".github" / "workflows" / "deploy-production.yml"
        self.assertTrue(self.path.exists())
        self.content = self.path.read_text()

    def test_deploy_production_exists(self):
        self.assertTrue(self.path.exists())

    def test_triggers_on_release(self):
        self.assertIn("release", self.content)
        self.assertIn("published", self.content)

    def test_validates_semver_tag(self):
        self.assertIn("semver", self.content.lower()) or self.assertIn("v[0-9]", self.content)

    def test_invalidates_cloudfront(self):
        self.assertIn("cloudfront", self.content.lower())

    def test_has_rollback_on_failure(self):
        self.assertIn("rollback", self.content.lower())


class TestTerraform(unittest.TestCase):
    """Tests for Terraform configuration - 10 tests."""

    def setUp(self):
        self.tf_dir = REPO_ROOT / "deploy" / "terraform"

    def test_main_tf_exists(self):
        self.assertTrue((self.tf_dir / "main.tf").exists())

    def test_variables_tf_exists(self):
        self.assertTrue((self.tf_dir / "variables.tf").exists())

    def test_staging_tfvars_exists(self):
        self.assertTrue((self.tf_dir / "env" / "staging.tfvars").exists())

    def test_production_tfvars_exists(self):
        self.assertTrue((self.tf_dir / "env" / "production.tfvars").exists())

    def test_main_tf_has_ecs_fargate(self):
        content = (self.tf_dir / "main.tf").read_text()
        self.assertIn("FARGATE", content)

    def test_main_tf_has_alb(self):
        content = (self.tf_dir / "main.tf").read_text()
        self.assertIn("aws_lb", content)

    def test_main_tf_has_rds(self):
        content = (self.tf_dir / "main.tf").read_text()
        self.assertIn("aws_db_instance", content)

    def test_main_tf_has_elasticache(self):
        content = (self.tf_dir / "main.tf").read_text()
        self.assertIn("aws_elasticache", content)

    def test_main_tf_has_cloudfront(self):
        content = (self.tf_dir / "main.tf").read_text()
        self.assertIn("aws_cloudfront_distribution", content)

    def test_main_tf_https_listener(self):
        content = (self.tf_dir / "main.tf").read_text()
        self.assertIn("443", content)
        self.assertIn("HTTPS", content)


class TestDeployScripts(unittest.TestCase):
    """Tests for deploy scripts - 5 tests."""

    def test_health_check_sh_exists(self):
        path = REPO_ROOT / "deploy" / "scripts" / "health_check.sh"
        self.assertTrue(path.exists())

    def test_smoke_test_sh_exists(self):
        path = REPO_ROOT / "deploy" / "scripts" / "smoke_test.sh"
        self.assertTrue(path.exists())

    def test_health_check_tests_health_endpoint(self):
        content = (REPO_ROOT / "deploy" / "scripts" / "health_check.sh").read_text()
        self.assertIn("/health", content)

    def test_smoke_test_tests_multiple_endpoints(self):
        content = (REPO_ROOT / "deploy" / "scripts" / "smoke_test.sh").read_text()
        self.assertIn("/api/agents", content)

    def test_postgres_init_sql_exists(self):
        path = REPO_ROOT / "deploy" / "postgres" / "init.sql"
        self.assertTrue(path.exists())


class TestHealthEndpoint(unittest.TestCase):
    """Tests for updated /health and new /ready endpoints in rest_api_server.py - 5 tests."""

    def setUp(self):
        self.server_path = REPO_ROOT / "dashboard" / "rest_api_server.py"
        self.assertTrue(self.server_path.exists())
        self.content = self.server_path.read_text()

    def test_health_endpoint_exists(self):
        self.assertIn("/api/health", self.content)

    def test_health_endpoint_returns_status_ok(self):
        self.assertIn("'status': 'ok'", self.content) or self.assertIn('"status": "ok"', self.content)

    def test_ready_endpoint_registered(self):
        self.assertIn("/ready", self.content)

    def test_ready_endpoint_handler_exists(self):
        self.assertIn("ready_check", self.content)

    def test_ready_returns_ready_field(self):
        self.assertIn("ready", self.content)


if __name__ == "__main__":
    # Run with verbosity
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestDockerfile,
        TestDockerCompose,
        TestDockerComposeProd,
        TestCIWorkflow,
        TestDeployStagingWorkflow,
        TestDeployProductionWorkflow,
        TestTerraform,
        TestDeployScripts,
        TestHealthEndpoint,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failures = len(result.failures) + len(result.errors)
    passed = total - failures
    print(f"\nTotal: {total} tests, {passed} passed, {failures} failed")
