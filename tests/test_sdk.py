"""Comprehensive tests for the Agent-Engineers SDK (AI-252).

Covers:
  - AgentDefinition validation, serialisation, and round-trip
  - AgentRegistry org-scoped lookup, load_from_dict, load_from_file (YAML/JSON)
  - MockOrchestrator run_agent, history, assertions
  - BaseBridge format_system_prompt and abstract interface
  - CLI init / test / validate commands (direct function call)
  - REST API registry endpoints (register, list, get, delete)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure repo root is on the path so `sdk` package is importable.
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sdk.agent_definition import AgentDefinition
from sdk.registry import AgentRegistry
from sdk.mock_orchestrator import MockOrchestrator
from sdk.base_bridge import BaseBridge


# ===========================================================================
# Fixtures & helpers
# ===========================================================================

def _make_agent(**kwargs: Any) -> AgentDefinition:
    defaults = {
        "name": "test-agent",
        "title": "Test Agent",
        "system_prompt": "You are a test agent.",
        "model": "sonnet",
    }
    defaults.update(kwargs)
    return AgentDefinition(**defaults)


@pytest.fixture()
def agent() -> AgentDefinition:
    return _make_agent()


@pytest.fixture()
def registry() -> AgentRegistry:
    return AgentRegistry()


@pytest.fixture()
def populated_registry(registry: AgentRegistry, agent: AgentDefinition) -> AgentRegistry:
    registry.register(agent)
    return registry


@pytest.fixture()
def orchestrator(populated_registry: AgentRegistry) -> MockOrchestrator:
    return MockOrchestrator(populated_registry)


# ===========================================================================
# AgentDefinition — validation
# ===========================================================================

class TestAgentDefinitionValidation:
    def test_valid_agent_no_errors(self, agent: AgentDefinition) -> None:
        assert agent.validate() == []

    def test_missing_name(self) -> None:
        a = _make_agent(name="")
        errors = a.validate()
        assert any("name" in e for e in errors)

    def test_missing_title(self) -> None:
        a = _make_agent(title="")
        errors = a.validate()
        assert any("title" in e for e in errors)

    def test_missing_system_prompt(self) -> None:
        a = _make_agent(system_prompt="")
        errors = a.validate()
        assert any("system_prompt" in e for e in errors)

    def test_invalid_model(self) -> None:
        a = _make_agent(model="gpt-99")
        errors = a.validate()
        assert any("model" in e for e in errors)

    def test_valid_models(self) -> None:
        for model in ("haiku", "sonnet", "opus", "inherit"):
            a = _make_agent(model=model)
            assert a.validate() == [], f"model={model!r} should be valid"

    def test_tools_not_list(self) -> None:
        a = _make_agent(tools="Read")  # type: ignore[arg-type]
        errors = a.validate()
        assert any("tools" in e for e in errors)

    def test_tools_non_string_items(self) -> None:
        a = _make_agent(tools=[1, 2])  # type: ignore[list-item]
        errors = a.validate()
        assert any("tool" in e for e in errors)

    def test_git_identity_missing_keys(self) -> None:
        a = _make_agent(git_identity={"name": "Bot"})  # missing "email"
        errors = a.validate()
        assert any("email" in e for e in errors)

    def test_git_identity_not_dict(self) -> None:
        a = _make_agent(git_identity="invalid")  # type: ignore[arg-type]
        errors = a.validate()
        assert any("git_identity" in e for e in errors)

    def test_valid_git_identity(self) -> None:
        a = _make_agent(git_identity={"name": "Bot", "email": "bot@example.com"})
        assert a.validate() == []

    def test_multiple_errors(self) -> None:
        a = _make_agent(name="", title="", system_prompt="", model="bad")
        errors = a.validate()
        assert len(errors) >= 4

    def test_whitespace_only_name(self) -> None:
        a = _make_agent(name="   ")
        errors = a.validate()
        assert any("name" in e for e in errors)


# ===========================================================================
# AgentDefinition — serialisation
# ===========================================================================

class TestAgentDefinitionSerialisation:
    def test_to_dict_contains_all_fields(self, agent: AgentDefinition) -> None:
        d = agent.to_dict()
        expected = {"name", "title", "system_prompt", "model", "tools",
                    "git_identity", "version", "description", "org_id"}
        assert expected.issubset(d.keys())

    def test_to_dict_values(self, agent: AgentDefinition) -> None:
        d = agent.to_dict()
        assert d["name"] == "test-agent"
        assert d["title"] == "Test Agent"
        assert d["model"] == "sonnet"

    def test_from_dict_round_trip(self, agent: AgentDefinition) -> None:
        d = agent.to_dict()
        restored = AgentDefinition.from_dict(d)
        assert restored.name == agent.name
        assert restored.title == agent.title
        assert restored.system_prompt == agent.system_prompt
        assert restored.model == agent.model
        assert restored.tools == agent.tools
        assert restored.version == agent.version
        assert restored.description == agent.description
        assert restored.org_id == agent.org_id

    def test_from_dict_ignores_unknown_keys(self) -> None:
        d = {
            "name": "x",
            "title": "X",
            "system_prompt": "test",
            "unknown_future_field": "ignored",
        }
        a = AgentDefinition.from_dict(d)
        assert a.name == "x"

    def test_to_json_is_valid_json(self, agent: AgentDefinition) -> None:
        json_str = agent.to_json()
        parsed = json.loads(json_str)
        assert parsed["name"] == "test-agent"

    def test_from_json_round_trip(self, agent: AgentDefinition) -> None:
        json_str = agent.to_json()
        restored = AgentDefinition.from_json(json_str)
        assert restored.name == agent.name
        assert restored.system_prompt == agent.system_prompt

    def test_default_fields(self) -> None:
        a = AgentDefinition(
            name="minimal",
            title="Minimal",
            system_prompt="prompt",
        )
        assert a.model == "sonnet"
        assert a.tools == []
        assert a.version == "0.1.0"
        assert a.description == ""
        assert a.org_id is None
        assert a.git_identity is None


# ===========================================================================
# AgentRegistry
# ===========================================================================

class TestAgentRegistry:
    def test_register_and_get_public(self, registry: AgentRegistry, agent: AgentDefinition) -> None:
        registry.register(agent)
        fetched = registry.get("test-agent")
        assert fetched.name == "test-agent"

    def test_get_missing_raises_key_error(self, registry: AgentRegistry) -> None:
        with pytest.raises(KeyError, match="test-agent"):
            registry.get("test-agent")

    def test_private_agent_scoped_to_org(self, registry: AgentRegistry) -> None:
        private = _make_agent(name="private-agent", org_id="org-A")
        registry.register(private, org_id="org-A")

        # Should be accessible to org-A
        fetched = registry.get("private-agent", org_id="org-A")
        assert fetched.name == "private-agent"

        # Should NOT be accessible to org-B
        with pytest.raises(KeyError):
            registry.get("private-agent", org_id="org-B")

    def test_public_agent_visible_to_all_orgs(self, registry: AgentRegistry, agent: AgentDefinition) -> None:
        registry.register(agent)  # no org_id → public
        fetched_a = registry.get("test-agent", org_id="org-A")
        fetched_b = registry.get("test-agent", org_id="org-B")
        assert fetched_a.name == fetched_b.name == "test-agent"

    def test_private_overrides_public_for_org(self, registry: AgentRegistry) -> None:
        public_agent = _make_agent(name="shared", system_prompt="public prompt")
        private_agent = _make_agent(name="shared", system_prompt="private prompt", org_id="org-A")

        registry.register(public_agent)
        registry.register(private_agent, org_id="org-A")

        # org-A gets private version
        assert registry.get("shared", org_id="org-A").system_prompt == "private prompt"
        # others get public
        assert registry.get("shared", org_id="org-B").system_prompt == "public prompt"

    def test_list_agents_includes_public_and_org_private(self, registry: AgentRegistry) -> None:
        public = _make_agent(name="pub")
        private = _make_agent(name="priv", org_id="org-A")
        other_org = _make_agent(name="other", org_id="org-B")

        registry.register(public)
        registry.register(private, org_id="org-A")
        registry.register(other_org, org_id="org-B")

        agents_for_a = registry.list_agents(org_id="org-A")
        names = {a.name for a in agents_for_a}
        assert "pub" in names
        assert "priv" in names
        assert "other" not in names

    def test_list_agents_no_org_returns_all(self, registry: AgentRegistry) -> None:
        for i in range(3):
            registry.register(_make_agent(name=f"agent-{i}"))
        all_agents = registry.list_agents()
        assert len(all_agents) == 3

    def test_unregister_removes_agent(self, registry: AgentRegistry, agent: AgentDefinition) -> None:
        registry.register(agent)
        registry.unregister("test-agent")
        with pytest.raises(KeyError):
            registry.get("test-agent")

    def test_unregister_missing_is_noop(self, registry: AgentRegistry) -> None:
        # Should not raise
        registry.unregister("does-not-exist")

    def test_clear_all(self, registry: AgentRegistry) -> None:
        for i in range(3):
            registry.register(_make_agent(name=f"a-{i}"))
        registry.clear()
        assert registry.list_agents() == []

    def test_clear_org_only(self, registry: AgentRegistry) -> None:
        public = _make_agent(name="pub")
        private = _make_agent(name="priv", org_id="org-A")
        registry.register(public)
        registry.register(private, org_id="org-A")

        registry.clear(org_id="org-A")

        assert registry.list_agents() == [registry.get("pub")]

    def test_load_from_dict(self, registry: AgentRegistry) -> None:
        data = {
            "name": "from-dict",
            "title": "From Dict",
            "system_prompt": "loaded from dict",
        }
        agent = registry.load_from_dict(data)
        assert agent.name == "from-dict"
        # Should be registered
        assert registry.get("from-dict").name == "from-dict"

    def test_load_from_file_json(self, registry: AgentRegistry, tmp_path: Path) -> None:
        data = {
            "name": "json-agent",
            "title": "JSON Agent",
            "system_prompt": "loaded from JSON",
        }
        json_file = tmp_path / "agent.json"
        json_file.write_text(json.dumps(data))

        agent = registry.load_from_file(str(json_file))
        assert agent.name == "json-agent"
        assert registry.get("json-agent").name == "json-agent"

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("yaml"),
        reason="PyYAML not installed",
    )
    def test_load_from_file_yaml(self, registry: AgentRegistry, tmp_path: Path) -> None:
        yaml_content = (
            "name: yaml-agent\n"
            "title: YAML Agent\n"
            "system_prompt: loaded from YAML\n"
        )
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text(yaml_content)

        agent = registry.load_from_file(str(yaml_file))
        assert agent.name == "yaml-agent"
        assert registry.get("yaml-agent").name == "yaml-agent"

    def test_load_from_file_unsupported_extension(self, registry: AgentRegistry, tmp_path: Path) -> None:
        bad_file = tmp_path / "agent.toml"
        bad_file.write_text("name = 'x'")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            registry.load_from_file(str(bad_file))

    def test_export_registry_json_serialisable(self, registry: AgentRegistry) -> None:
        registry.register(_make_agent(name="a"))
        registry.register(_make_agent(name="b", org_id="org-1"), org_id="org-1")

        exported = registry.export_registry()
        # Should be JSON-serialisable
        serialised = json.dumps(exported)
        parsed = json.loads(serialised)
        assert parsed["count"] >= 1

    def test_export_registry_org_scoped(self, registry: AgentRegistry) -> None:
        registry.register(_make_agent(name="public"))
        registry.register(_make_agent(name="private-a", org_id="org-A"), org_id="org-A")
        registry.register(_make_agent(name="private-b", org_id="org-B"), org_id="org-B")

        export_a = registry.export_registry(org_id="org-A")
        names = {a["name"] for a in export_a["agents"]}
        assert "public" in names
        assert "private-a" in names
        assert "private-b" not in names


# ===========================================================================
# MockOrchestrator
# ===========================================================================

class TestMockOrchestrator:
    def test_run_agent_returns_result(self, orchestrator: MockOrchestrator) -> None:
        result = orchestrator.run_agent("test-agent", {"ticket": "AI-001"})
        assert result["agent_name"] == "test-agent"
        assert result["status"] == "completed"
        assert "output" in result
        assert "timestamp" in result

    def test_run_agent_records_task(self, orchestrator: MockOrchestrator) -> None:
        task = {"ticket": "AI-999", "action": "review"}
        orchestrator.run_agent("test-agent", task)
        history = orchestrator.get_run_history()
        assert len(history) == 1
        assert history[0]["task"] == task

    def test_run_agent_unknown_raises_key_error(self, orchestrator: MockOrchestrator) -> None:
        with pytest.raises(KeyError):
            orchestrator.run_agent("nonexistent-agent", {})

    def test_get_run_history_empty_initially(self, populated_registry: AgentRegistry) -> None:
        orch = MockOrchestrator(populated_registry)
        assert orch.get_run_history() == []

    def test_get_run_history_multiple_runs(self, orchestrator: MockOrchestrator) -> None:
        orchestrator.run_agent("test-agent", {"n": 1})
        orchestrator.run_agent("test-agent", {"n": 2})
        orchestrator.run_agent("test-agent", {"n": 3})
        assert len(orchestrator.get_run_history()) == 3

    def test_assert_agent_ran_passes(self, orchestrator: MockOrchestrator) -> None:
        orchestrator.run_agent("test-agent", {})
        orchestrator.assert_agent_ran("test-agent")  # should not raise

    def test_assert_agent_ran_fails(self, orchestrator: MockOrchestrator) -> None:
        with pytest.raises(AssertionError, match="other-agent"):
            orchestrator.assert_agent_ran("other-agent")

    def test_assert_task_contains_passes(self, orchestrator: MockOrchestrator) -> None:
        orchestrator.run_agent("test-agent", {"key": "value", "num": 42})
        orchestrator.assert_task_contains("key", "value")
        orchestrator.assert_task_contains("num", 42)

    def test_assert_task_contains_fails(self, orchestrator: MockOrchestrator) -> None:
        orchestrator.run_agent("test-agent", {"key": "wrong"})
        with pytest.raises(AssertionError):
            orchestrator.assert_task_contains("key", "expected")

    def test_reset_clears_history(self, orchestrator: MockOrchestrator) -> None:
        orchestrator.run_agent("test-agent", {})
        orchestrator.reset()
        assert orchestrator.get_run_history() == []

    def test_result_contains_agent_model(self, orchestrator: MockOrchestrator) -> None:
        result = orchestrator.run_agent("test-agent", {})
        assert result["agent_model"] == "sonnet"

    def test_result_contains_org_id(self, populated_registry: AgentRegistry) -> None:
        orch = MockOrchestrator(populated_registry)
        result = orch.run_agent("test-agent", {}, org_id="org-X")
        assert result["org_id"] == "org-X"


# ===========================================================================
# BaseBridge
# ===========================================================================

class _ConcreteTestBridge(BaseBridge):
    """Minimal concrete implementation for testing."""

    @property
    def name(self) -> str:
        return "test-bridge"

    def generate(self, prompt: str, model: str) -> str:
        return f"[{model}] Response to: {prompt}"

    def get_model_info(self) -> dict:
        return {"provider": "test", "models": ["test-model"]}


class TestBaseBridge:
    def test_concrete_bridge_is_instantiable(self) -> None:
        bridge = _ConcreteTestBridge()
        assert bridge.name == "test-bridge"

    def test_generate_returns_string(self) -> None:
        bridge = _ConcreteTestBridge()
        result = bridge.generate("hello", "sonnet")
        assert isinstance(result, str)
        assert "hello" in result

    def test_get_model_info_returns_dict(self) -> None:
        bridge = _ConcreteTestBridge()
        info = bridge.get_model_info()
        assert isinstance(info, dict)
        assert "provider" in info
        assert "models" in info

    def test_format_system_prompt_replaces_placeholders(self) -> None:
        bridge = _ConcreteTestBridge()
        template = "You are working on ticket {ticket_id} for org {org}."
        result = bridge.format_system_prompt(template, {"ticket_id": "AI-42", "org": "Acme"})
        assert result == "You are working on ticket AI-42 for org Acme."

    def test_format_system_prompt_missing_key_preserved(self) -> None:
        bridge = _ConcreteTestBridge()
        template = "Ticket {ticket_id} is {status}."
        result = bridge.format_system_prompt(template, {"ticket_id": "AI-1"})
        # {status} should remain untouched
        assert "{status}" in result
        assert "AI-1" in result

    def test_format_system_prompt_empty_context(self) -> None:
        bridge = _ConcreteTestBridge()
        template = "No placeholders here."
        result = bridge.format_system_prompt(template, {})
        assert result == template

    def test_abstract_bridge_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            BaseBridge()  # type: ignore[abstract]

    def test_format_system_prompt_numeric_values(self) -> None:
        bridge = _ConcreteTestBridge()
        template = "Budget: {budget} tokens."
        result = bridge.format_system_prompt(template, {"budget": 1000})
        assert "1000" in result


# ===========================================================================
# CLI commands — direct function call
# ===========================================================================

class TestCLIInit:
    def test_init_creates_agent_yaml(self, tmp_path: Path) -> None:
        from sdk.cli import init
        import argparse
        args = argparse.Namespace(output_dir=str(tmp_path), force=False)
        exit_code = init(args)
        assert exit_code == 0
        assert (tmp_path / "agent.yaml").exists()

    def test_init_creates_readme(self, tmp_path: Path) -> None:
        from sdk.cli import init
        import argparse
        args = argparse.Namespace(output_dir=str(tmp_path), force=False)
        init(args)
        assert (tmp_path / "README.md").exists()

    def test_init_refuses_overwrite_without_force(self, tmp_path: Path) -> None:
        from sdk.cli import init
        import argparse
        (tmp_path / "agent.yaml").write_text("existing")
        args = argparse.Namespace(output_dir=str(tmp_path), force=False)
        exit_code = init(args)
        assert exit_code != 0

    def test_init_force_overwrites(self, tmp_path: Path) -> None:
        from sdk.cli import init
        import argparse
        (tmp_path / "agent.yaml").write_text("old content")
        args = argparse.Namespace(output_dir=str(tmp_path), force=True)
        exit_code = init(args)
        assert exit_code == 0
        content = (tmp_path / "agent.yaml").read_text()
        assert "my-custom-agent" in content


class TestCLIValidate:
    def _write_yaml(self, tmp_path: Path, content: str) -> str:
        p = tmp_path / "agent.yaml"
        p.write_text(content)
        return str(p)

    def test_validate_valid_agent(self, tmp_path: Path) -> None:
        from sdk.cli import validate
        import argparse
        yaml_content = (
            "name: cli-agent\n"
            "title: CLI Agent\n"
            "system_prompt: Test prompt\n"
            "model: haiku\n"
        )
        f = self._write_yaml(tmp_path, yaml_content)
        old_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            args = argparse.Namespace(file=f)
            exit_code = validate(args)
        finally:
            os.chdir(old_dir)
        assert exit_code == 0

    def test_validate_invalid_agent(self, tmp_path: Path) -> None:
        from sdk.cli import validate
        import argparse
        yaml_content = "name: \"\"\ntitle: \"\"\nsystem_prompt: \"\"\nmodel: bad-model\n"
        f = self._write_yaml(tmp_path, yaml_content)
        old_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            args = argparse.Namespace(file=f)
            exit_code = validate(args)
        finally:
            os.chdir(old_dir)
        assert exit_code != 0

    def test_validate_json_file(self, tmp_path: Path) -> None:
        from sdk.cli import validate
        import argparse
        data = {"name": "json-cli", "title": "JSON CLI", "system_prompt": "ok", "model": "sonnet"}
        f = tmp_path / "agent.json"
        f.write_text(json.dumps(data))
        args = argparse.Namespace(file=str(f))
        exit_code = validate(args)
        assert exit_code == 0


class TestCLITest:
    def test_test_command_valid(self, tmp_path: Path) -> None:
        from sdk.cli import test as cli_test
        import argparse
        yaml_content = (
            "name: run-agent\n"
            "title: Run Agent\n"
            "system_prompt: Test prompt\n"
            "model: sonnet\n"
        )
        f = tmp_path / "agent.yaml"
        f.write_text(yaml_content)
        args = argparse.Namespace(file=str(f), task='{"ticket": "AI-001"}')
        exit_code = cli_test(args)
        assert exit_code == 0

    def test_test_command_invalid_task_json(self, tmp_path: Path) -> None:
        from sdk.cli import test as cli_test
        import argparse
        yaml_content = (
            "name: run-agent\n"
            "title: Run Agent\n"
            "system_prompt: Test prompt\n"
            "model: sonnet\n"
        )
        f = tmp_path / "agent.yaml"
        f.write_text(yaml_content)
        args = argparse.Namespace(file=str(f), task="{not valid json}")
        exit_code = cli_test(args)
        assert exit_code != 0

    def test_test_command_invalid_agent(self, tmp_path: Path) -> None:
        from sdk.cli import test as cli_test
        import argparse
        yaml_content = "name: \"\"\ntitle: \"\"\nsystem_prompt: \"\"\nmodel: bad\n"
        f = tmp_path / "agent.yaml"
        f.write_text(yaml_content)
        args = argparse.Namespace(file=str(f), task="{}")
        exit_code = cli_test(args)
        assert exit_code != 0


class TestCLILoadAgent:
    def test_no_agent_file_exits(self, tmp_path: Path) -> None:
        from sdk.cli import _load_agent_file
        old_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(SystemExit):
                _load_agent_file(None)
        finally:
            os.chdir(old_dir)

    def test_explicit_file_path(self, tmp_path: Path) -> None:
        from sdk.cli import _load_agent_file
        data = {"name": "x", "title": "X", "system_prompt": "p"}
        f = tmp_path / "custom.json"
        f.write_text(json.dumps(data))
        agent = _load_agent_file(str(f))
        assert agent.name == "x"


# ===========================================================================
# REST API registry endpoints (aiohttp test client)
# ===========================================================================

try:
    from aiohttp.test_utils import TestClient, TestServer
    from aiohttp import web as _web
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False


@pytest.mark.skipif(not _AIOHTTP_AVAILABLE, reason="aiohttp not available")
class TestRegistryRestAPI:
    """Tests for the /api/registry/agents endpoints added in AI-252."""

    @pytest.fixture()
    def fresh_registry(self) -> AgentRegistry:
        return AgentRegistry()

    def _make_app(self, fresh_reg: AgentRegistry) -> Any:
        """Create a minimal aiohttp app with just the registry routes."""
        import dashboard.rest_api_server as rest_mod

        # Patch the module-level registry singleton so each test is isolated.
        rest_mod._sdk_registry = fresh_reg

        from dashboard.rest_api_server import RESTAPIServer
        # We need a server instance but without starting it
        server = RESTAPIServer.__new__(RESTAPIServer)
        server.app = _web.Application()
        server.app.router.add_get(
            '/api/registry/agents', server.registry_list_agents.__get__(server, RESTAPIServer)
        )
        server.app.router.add_post(
            '/api/registry/agents', server.registry_register_agent.__get__(server, RESTAPIServer)
        )
        server.app.router.add_get(
            '/api/registry/agents/{name}', server.registry_get_agent.__get__(server, RESTAPIServer)
        )
        server.app.router.add_delete(
            '/api/registry/agents/{name}', server.registry_unregister_agent.__get__(server, RESTAPIServer)
        )
        return server.app

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, fresh_registry: AgentRegistry) -> None:
        app = self._make_app(fresh_registry)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/registry/agents')
            assert resp.status == 200
            data = await resp.json()
            assert data["count"] == 0
            assert data["agents"] == []

    @pytest.mark.asyncio
    async def test_register_agent(self, fresh_registry: AgentRegistry) -> None:
        app = self._make_app(fresh_registry)
        payload = {
            "name": "api-agent",
            "title": "API Agent",
            "system_prompt": "You are a test agent.",
            "model": "haiku",
        }
        async with TestClient(TestServer(app)) as client:
            resp = await client.post('/api/registry/agents', json=payload)
            assert resp.status == 201
            data = await resp.json()
            assert data["status"] == "registered"
            assert data["agent"]["name"] == "api-agent"

    @pytest.mark.asyncio
    async def test_register_then_list(self, fresh_registry: AgentRegistry) -> None:
        app = self._make_app(fresh_registry)
        payload = {
            "name": "listed-agent",
            "title": "Listed Agent",
            "system_prompt": "I will be listed.",
        }
        async with TestClient(TestServer(app)) as client:
            await client.post('/api/registry/agents', json=payload)
            resp = await client.get('/api/registry/agents')
            data = await resp.json()
            names = [a["name"] for a in data["agents"]]
            assert "listed-agent" in names

    @pytest.mark.asyncio
    async def test_register_invalid_agent(self, fresh_registry: AgentRegistry) -> None:
        app = self._make_app(fresh_registry)
        payload = {
            "name": "",
            "title": "",
            "system_prompt": "",
            "model": "bad-model",
        }
        async with TestClient(TestServer(app)) as client:
            resp = await client.post('/api/registry/agents', json=payload)
            assert resp.status == 422
            data = await resp.json()
            assert "details" in data

    @pytest.mark.asyncio
    async def test_get_agent(self, fresh_registry: AgentRegistry) -> None:
        app = self._make_app(fresh_registry)
        payload = {
            "name": "fetch-me",
            "title": "Fetch Me",
            "system_prompt": "fetchable",
        }
        async with TestClient(TestServer(app)) as client:
            await client.post('/api/registry/agents', json=payload)
            resp = await client.get('/api/registry/agents/fetch-me')
            assert resp.status == 200
            data = await resp.json()
            assert data["name"] == "fetch-me"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, fresh_registry: AgentRegistry) -> None:
        app = self._make_app(fresh_registry)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get('/api/registry/agents/ghost')
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_delete_agent(self, fresh_registry: AgentRegistry) -> None:
        app = self._make_app(fresh_registry)
        payload = {
            "name": "deletable",
            "title": "Deletable",
            "system_prompt": "delete me",
        }
        async with TestClient(TestServer(app)) as client:
            await client.post('/api/registry/agents', json=payload)
            resp = await client.delete('/api/registry/agents/deletable')
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "unregistered"

            # Should no longer be in list
            list_resp = await client.get('/api/registry/agents')
            list_data = await list_resp.json()
            assert list_data["count"] == 0

    @pytest.mark.asyncio
    async def test_invalid_json_body(self, fresh_registry: AgentRegistry) -> None:
        app = self._make_app(fresh_registry)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                '/api/registry/agents',
                data="not-json",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_list_agents_org_filter(self, fresh_registry: AgentRegistry) -> None:
        app = self._make_app(fresh_registry)
        public_payload = {
            "name": "public-a",
            "title": "Public A",
            "system_prompt": "public",
        }
        private_payload = {
            "name": "private-a",
            "title": "Private A",
            "system_prompt": "private",
            "org_id": "org-1",
        }
        async with TestClient(TestServer(app)) as client:
            await client.post('/api/registry/agents', json=public_payload)
            await client.post('/api/registry/agents', json=private_payload)

            resp = await client.get('/api/registry/agents?org_id=org-1')
            data = await resp.json()
            names = {a["name"] for a in data["agents"]}
            assert "public-a" in names
            assert "private-a" in names

            resp2 = await client.get('/api/registry/agents?org_id=org-2')
            data2 = await resp2.json()
            names2 = {a["name"] for a in data2["agents"]}
            assert "public-a" in names2
            assert "private-a" not in names2


# ===========================================================================
# SDK __init__ exports
# ===========================================================================

class TestSDKInitExports:
    def test_imports_from_sdk(self) -> None:
        import sdk
        assert hasattr(sdk, "AgentDefinition")
        assert hasattr(sdk, "AgentRegistry")
        assert hasattr(sdk, "MockOrchestrator")
        assert hasattr(sdk, "BaseBridge")

    def test_version(self) -> None:
        import sdk
        assert sdk.__version__ == "0.1.0"

    def test_all_list(self) -> None:
        import sdk
        for name in sdk.__all__:
            assert hasattr(sdk, name), f"sdk.{name} missing"


# ===========================================================================
# Example agent
# ===========================================================================

class TestSecurityReviewAgentExample:
    def test_example_agent_valid(self) -> None:
        from sdk.examples.security_review_agent import SECURITY_REVIEW_AGENT
        assert SECURITY_REVIEW_AGENT.name == "security-review"
        errors = SECURITY_REVIEW_AGENT.validate()
        assert errors == []

    def test_example_agent_has_tools(self) -> None:
        from sdk.examples.security_review_agent import SECURITY_REVIEW_AGENT
        assert len(SECURITY_REVIEW_AGENT.tools) > 0

    def test_example_agent_run_example(self, capsys: pytest.CaptureFixture) -> None:
        from sdk.examples.security_review_agent import run_example
        run_example()
        captured = capsys.readouterr()
        assert "SecurityReviewAgent" in captured.out
        assert "All assertions passed" in captured.out
