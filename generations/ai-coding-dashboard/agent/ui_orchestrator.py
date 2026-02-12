"""
UI Orchestrator - LLM-based component selection

Receives DashboardEvents from the event ingestion API and decides which A2UI
components to generate and emit.  Uses a lightweight LLM call (Claude Haiku)
for context-aware decisions, with a deterministic fallback if the LLM is
unavailable or returns an invalid response.

Usage:
    orchestrator = UIOrchestrator(api_base="http://localhost:8000")
    a2ui_message = await orchestrator.handle_event(event)
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from a2ui_generator import A2UIGenerator

logger = logging.getLogger(__name__)

# Default component mappings (fallback when LLM is unavailable)
DEFAULT_EVENT_MAPPING: Dict[str, List[str]] = {
    "task_started": ["TaskCard", "ActivityItem"],
    "task_completed": ["TaskCard", "ProgressRing", "ActivityItem"],
    "decision_needed": ["DecisionCard", "ActivityItem"],
    "approval_needed": ["ApprovalCard", "ActivityItem"],
    "error": ["ErrorCard", "ActivityItem"],
    "milestone": ["MilestoneCard", "ProgressRing", "ActivityItem"],
    "file_changed": ["FileTree", "ActivityItem"],
    "test_results": ["TestResults", "ActivityItem"],
    "activity": ["ActivityItem"],
}


class UIOrchestrator:
    """
    Orchestrates A2UI component generation in response to dashboard events.

    Receives events, determines the appropriate UI response, and emits
    A2UI messages for the frontend to render.
    """

    def __init__(
        self,
        api_base: str = "http://localhost:8000",
        use_llm: bool = True,
    ):
        self.api_base = api_base.rstrip("/")
        self.use_llm = use_llm
        self.gen = A2UIGenerator()
        self._event_count = 0

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def handle_event(
        self,
        event: Dict[str, Any],
        project_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a dashboard event and return an A2UI message.

        Args:
            event: DashboardEvent dict with at least {type, payload}
            project_state: Optional current project state for context

        Returns:
            A2UI message (surfaceUpdate) with generated components
        """
        event_type = event.get("type", "activity")
        payload = event.get("payload", {})
        self._event_count += 1

        logger.info("Handling event #%d: type=%s", self._event_count, event_type)

        if self.use_llm:
            try:
                components = await self._llm_decide(event_type, payload, project_state)
                if components:
                    return self.gen.surface_update(components)
            except Exception as exc:
                logger.warning("LLM decision failed, using fallback: %s", exc)

        # Deterministic fallback
        components = self._fallback_decide(event_type, payload, project_state)
        return self.gen.surface_update(components)

    # ------------------------------------------------------------------ #
    #  LLM-based decision
    # ------------------------------------------------------------------ #

    async def _llm_decide(
        self,
        event_type: str,
        payload: Dict[str, Any],
        project_state: Optional[Dict[str, Any]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Ask the LLM which components to generate for this event."""
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not available for LLM call")
            return None

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return None

        model = os.environ.get("OPENROUTER_HAIKU_MODEL", "anthropic/claude-haiku-4-5-20251001")
        prompt = self._build_llm_prompt(event_type, payload, project_state)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1024,
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        return self._parse_llm_response(content, event_type, payload)

    def _build_llm_prompt(
        self,
        event_type: str,
        payload: Dict[str, Any],
        project_state: Optional[Dict[str, Any]],
    ) -> str:
        component_catalog = [
            "TaskCard(title, status, category, progress, description, steps, agentNotes)",
            "ProgressRing(percentage, tasksCompleted, totalTasks, filesModified)",
            "ActivityItem(eventType, message, reasoning, timestamp)",
            "FileTree(files, activeFile, modifiedFiles)",
            "TestResults(tests, status, coverage)",
            "ApprovalCard(approvalId, action, riskLevel, context, affectedFiles)",
            "DecisionCard(decisionId, question, options, recommendation, context)",
            "MilestoneCard(title, summary, tasksCompleted, nextPhase, achievements)",
            "ErrorCard(errorId, message, details, recoveryOptions, stackTrace)",
        ]

        state_summary = ""
        if project_state:
            total = project_state.get("totalTasks", 0)
            completed = project_state.get("completedTasks", 0)
            state_summary = f"\nProject state: {completed}/{total} tasks completed."

        return f"""You are a UI orchestrator for an AI coding dashboard.
Given a dashboard event, decide which A2UI components to render.

Available components:
{chr(10).join('- ' + c for c in component_catalog)}

Event type: {event_type}
Payload: {json.dumps(payload, default=str)}
{state_summary}

Respond ONLY with a JSON array of component names to render (e.g. ["TaskCard","ActivityItem"]).
Choose 1-3 components that best represent this event. Always include ActivityItem for logging."""

    def _parse_llm_response(
        self,
        content: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Optional[List[Dict[str, Any]]]:
        """Parse LLM response into component list, then generate specs."""
        try:
            # Extract JSON array from response
            start = content.index("[")
            end = content.index("]") + 1
            component_names = json.loads(content[start:end])
        except (ValueError, json.JSONDecodeError):
            logger.warning("Could not parse LLM response: %s", content[:200])
            return None

        return self._generate_components(component_names, event_type, payload)

    # ------------------------------------------------------------------ #
    #  Deterministic fallback
    # ------------------------------------------------------------------ #

    def _fallback_decide(
        self,
        event_type: str,
        payload: Dict[str, Any],
        project_state: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Deterministic component selection based on event type."""
        component_names = DEFAULT_EVENT_MAPPING.get(event_type, ["ActivityItem"])
        return self._generate_components(component_names, event_type, payload)

    # ------------------------------------------------------------------ #
    #  Component generation from names
    # ------------------------------------------------------------------ #

    def _generate_components(
        self,
        component_names: List[str],
        event_type: str,
        payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate A2UI component specs from a list of component names."""
        components: List[Dict[str, Any]] = []
        event_id = payload.get("id", f"evt-{self._event_count}")

        for name in component_names:
            spec = self._generate_single(name, event_type, payload, event_id)
            if spec:
                components.append(spec)

        return components

    def _generate_single(
        self,
        name: str,
        event_type: str,
        payload: Dict[str, Any],
        event_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Generate a single component spec."""
        g = self.gen

        if name == "TaskCard":
            return g.task_card(
                task_id=payload.get("task_id", event_id),
                title=payload.get("title", payload.get("task_name", "Task")),
                status=payload.get("status", "in_progress"),
                category=payload.get("category"),
                progress=payload.get("progress", 0),
                description=payload.get("description"),
                steps=payload.get("steps"),
                agent_notes=payload.get("agent_notes"),
            )

        if name == "ProgressRing":
            return g.progress_ring(
                component_id=f"progress-{event_id}",
                percentage=payload.get("percentage", 0),
                tasks_completed=payload.get("tasks_completed", 0),
                total_tasks=payload.get("total_tasks", 1),
                files_modified=payload.get("files_modified", 0),
            )

        if name == "ActivityItem":
            return g.activity_item(
                event_id=f"activity-{event_id}",
                event_type=self._map_event_type(event_type),
                message=payload.get("message", payload.get("title", f"{event_type} event")),
                reasoning=payload.get("reasoning"),
                timestamp=payload.get("timestamp"),
            )

        if name == "FileTree":
            return g.file_tree(
                component_id=f"filetree-{event_id}",
                files=payload.get("files", []),
                active_file=payload.get("active_file"),
                modified_files=payload.get("modified_files"),
            )

        if name == "TestResults":
            return g.test_results(
                component_id=f"tests-{event_id}",
                tests=payload.get("tests", []),
                status=payload.get("test_status", "completed"),
                coverage=payload.get("coverage"),
            )

        if name == "ApprovalCard":
            return g.approval_card(
                approval_id=payload.get("approval_id", event_id),
                action=payload.get("action", "Unknown action"),
                risk_level=payload.get("risk_level", "medium"),
                context=payload.get("context", ""),
                affected_files=payload.get("affected_files"),
                estimated_impact=payload.get("estimated_impact"),
            )

        if name == "DecisionCard":
            return g.decision_card(
                decision_id=payload.get("decision_id", event_id),
                question=payload.get("question", "Decision needed"),
                options=payload.get("options", []),
                recommendation=payload.get("recommendation"),
                context=payload.get("context"),
            )

        if name == "MilestoneCard":
            return g.milestone_card(
                milestone_id=f"milestone-{event_id}",
                title=payload.get("title", "Milestone reached"),
                summary=payload.get("summary", ""),
                tasks_completed=payload.get("tasks_completed", 0),
                next_phase=payload.get("next_phase"),
                achievements=payload.get("achievements"),
            )

        if name == "ErrorCard":
            return g.error_card(
                error_id=payload.get("error_id", event_id),
                message=payload.get("message", "An error occurred"),
                details=payload.get("details"),
                recovery_options=payload.get("recovery_options"),
                stack_trace=payload.get("stack_trace"),
            )

        logger.warning("Unknown component name: %s", name)
        return None

    @staticmethod
    def _map_event_type(event_type: str) -> str:
        """Map dashboard event type to ActivityItem eventType."""
        mapping = {
            "task_started": "file",
            "task_completed": "milestone",
            "decision_needed": "decision",
            "approval_needed": "approval",
            "error": "error",
            "milestone": "milestone",
            "file_changed": "file",
            "test_results": "test",
            "activity": "command",
        }
        return mapping.get(event_type, "command")
