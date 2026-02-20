"""Agent-Engineers SDK — Public Python SDK for custom agent development.

Quick start::

    from sdk import AgentDefinition, AgentRegistry, MockOrchestrator, BaseBridge

    class MyAgent(AgentDefinition):
        pass

    registry = AgentRegistry()
    registry.register(AgentDefinition(
        name="my-agent",
        title="My Agent",
        system_prompt="You are a helpful assistant.",
    ))

    orchestrator = MockOrchestrator(registry)
    result = orchestrator.run_agent("my-agent", {"task": "hello"})
"""

from sdk.agent_definition import AgentDefinition
from sdk.registry import AgentRegistry
from sdk.mock_orchestrator import MockOrchestrator
from sdk.base_bridge import BaseBridge

__version__ = "0.1.0"
__all__ = [
    "AgentDefinition",
    "AgentRegistry",
    "MockOrchestrator",
    "BaseBridge",
    "__version__",
]
