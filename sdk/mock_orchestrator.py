"""MockOrchestrator — local unit-testing harness for custom agents."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sdk.registry import AgentRegistry


class MockOrchestrator:
    """Simulate agent execution for local testing.

    The :class:`MockOrchestrator` does not call any real AI provider.  It
    records each run in an in-memory history so that test assertions can
    verify that the correct agents were invoked with the expected tasks.

    Usage::

        registry = AgentRegistry()
        registry.register(my_agent)

        orchestrator = MockOrchestrator(registry)
        result = orchestrator.run_agent("my-agent", {"ticket": "AI-123"})
        orchestrator.assert_agent_ran("my-agent")
    """

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry
        self._run_history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_agent(
        self,
        agent_name: str,
        task: dict[str, Any],
        org_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Simulate running *agent_name* against *task*.

        Looks the agent up in the registry (using the same org-scoped lookup
        as the real orchestrator) and records the run in history.

        Parameters
        ----------
        agent_name:
            Name of the agent to run.
        task:
            Arbitrary task payload dict.
        org_id:
            Organisation context for the lookup.

        Returns
        -------
        dict
            A mock result dict containing ``agent_name``, ``task``,
            ``status``, ``output``, and ``timestamp``.

        Raises
        ------
        KeyError
            If no agent with *agent_name* is found in the registry.
        """
        agent = self._registry.get(agent_name, org_id=org_id)

        record: dict[str, Any] = {
            "agent_name": agent_name,
            "agent_title": agent.title,
            "agent_model": agent.model,
            "task": task,
            "org_id": org_id,
            "status": "completed",
            "output": f"[MockOrchestrator] Agent {agent_name!r} processed task successfully.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._run_history.append(record)
        return record

    # ------------------------------------------------------------------
    # History & assertions
    # ------------------------------------------------------------------

    def get_run_history(self) -> list[dict[str, Any]]:
        """Return all run records accumulated in this session."""
        return list(self._run_history)

    def assert_agent_ran(self, agent_name: str) -> None:
        """Raise :exc:`AssertionError` if *agent_name* was never run.

        Parameters
        ----------
        agent_name:
            The expected agent name.
        """
        ran = any(r["agent_name"] == agent_name for r in self._run_history)
        if not ran:
            names = sorted({r["agent_name"] for r in self._run_history})
            raise AssertionError(
                f"Expected agent {agent_name!r} to have been run, "
                f"but only these agents ran: {names}"
            )

    def assert_task_contains(self, key: str, value: Any) -> None:
        """Raise :exc:`AssertionError` if no run task contains *key=value*.

        Parameters
        ----------
        key:
            Key to look for in the task dict.
        value:
            Expected value for that key.
        """
        for record in self._run_history:
            if record["task"].get(key) == value:
                return
        raise AssertionError(
            f"No run found where task[{key!r}] == {value!r}. "
            f"Run history: {self._run_history}"
        )

    def reset(self) -> None:
        """Clear all run history."""
        self._run_history.clear()
