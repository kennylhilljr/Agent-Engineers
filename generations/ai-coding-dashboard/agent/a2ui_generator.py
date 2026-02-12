"""
A2UI JSON Generator

Generates A2UI-compliant JSON messages for the frontend to render.
Each generator function produces an A2UIComponentSpec that matches the v0.8 specification.

Usage:
    from a2ui_generator import A2UIGenerator

    gen = A2UIGenerator()
    msg = gen.surface_update([
        gen.task_card("task-1", "Initialize project", "in_progress", progress=45),
        gen.progress_ring("progress-1", 45, 3, 10),
    ])
"""

import uuid
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class A2UIGenerator:
    """Generates A2UI-compliant component specifications and messages."""

    # ------------------------------------------------------------------ #
    #  Component generators
    # ------------------------------------------------------------------ #

    @staticmethod
    def task_card(
        task_id: str,
        title: str,
        status: str,
        *,
        category: Optional[str] = None,
        progress: float = 0,
        description: Optional[str] = None,
        steps: Optional[List[str]] = None,
        agent_notes: Optional[str] = None,
        estimated_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {"title": title, "status": status}
        if category:
            props["category"] = category
        if progress:
            props["progress"] = progress
        if description:
            props["description"] = description
        if steps:
            props["steps"] = steps
        if agent_notes:
            props["agentNotes"] = agent_notes
        if estimated_time:
            props["estimatedTime"] = estimated_time
        return {"type": "a2ui.TaskCard", "id": task_id, "props": props}

    @staticmethod
    def progress_ring(
        component_id: str,
        percentage: float,
        tasks_completed: int,
        total_tasks: int,
        *,
        files_modified: int = 0,
        commands_run: int = 0,
        label: Optional[str] = None,
        size: str = "medium",
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "percentage": percentage,
            "tasksCompleted": tasks_completed,
            "totalTasks": total_tasks,
            "size": size,
        }
        if files_modified:
            props["filesModified"] = files_modified
        if commands_run:
            props["commandsRun"] = commands_run
        if label:
            props["label"] = label
        return {"type": "a2ui.ProgressRing", "id": component_id, "props": props}

    @staticmethod
    def activity_item(
        event_id: str,
        event_type: str,
        message: str,
        *,
        reasoning: Optional[str] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "eventType": event_type,
            "message": message,
            "timestamp": timestamp or datetime.now().isoformat(),
        }
        if reasoning:
            props["reasoning"] = reasoning
        if metadata:
            props["metadata"] = metadata
        return {"type": "a2ui.ActivityItem", "id": event_id, "props": props}

    @staticmethod
    def file_tree(
        component_id: str,
        files: List[Dict[str, Any]],
        *,
        active_file: Optional[str] = None,
        modified_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {"files": files}
        if active_file:
            props["activeFile"] = active_file
        if modified_files:
            props["modifiedFiles"] = modified_files
        return {"type": "a2ui.FileTree", "id": component_id, "props": props}

    @staticmethod
    def test_results(
        component_id: str,
        tests: List[Dict[str, Any]],
        status: str,
        *,
        coverage: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {"tests": tests, "status": status}
        if coverage:
            props["coverage"] = coverage
        return {"type": "a2ui.TestResults", "id": component_id, "props": props}

    @staticmethod
    def approval_card(
        approval_id: str,
        action: str,
        risk_level: str,
        context: str,
        *,
        affected_files: Optional[List[str]] = None,
        estimated_impact: Optional[str] = None,
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "approvalId": approval_id,
            "action": action,
            "riskLevel": risk_level,
            "context": context,
            "isPending": True,
        }
        if affected_files:
            props["affectedFiles"] = affected_files
        if estimated_impact:
            props["estimatedImpact"] = estimated_impact
        return {"type": "a2ui.ApprovalCard", "id": approval_id, "props": props}

    @staticmethod
    def decision_card(
        decision_id: str,
        question: str,
        options: List[Dict[str, Any]],
        *,
        recommendation: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "decisionId": decision_id,
            "question": question,
            "options": options,
            "isPending": True,
        }
        if recommendation:
            props["recommendation"] = recommendation
        if context:
            props["context"] = context
        return {"type": "a2ui.DecisionCard", "id": decision_id, "props": props}

    @staticmethod
    def milestone_card(
        milestone_id: str,
        title: str,
        summary: str,
        tasks_completed: int,
        *,
        next_phase: Optional[str] = None,
        achievements: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "title": title,
            "summary": summary,
            "tasksCompleted": tasks_completed,
            "timestamp": datetime.now().isoformat(),
        }
        if next_phase:
            props["nextPhase"] = next_phase
        if achievements:
            props["achievements"] = achievements
        return {"type": "a2ui.MilestoneCard", "id": milestone_id, "props": props}

    @staticmethod
    def error_card(
        error_id: str,
        message: str,
        *,
        details: Optional[str] = None,
        recovery_options: Optional[List[Dict[str, str]]] = None,
        stack_trace: Optional[str] = None,
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "errorId": error_id,
            "message": message,
            "isPending": True,
        }
        if details:
            props["details"] = details
        if recovery_options:
            props["recoveryOptions"] = recovery_options
        if stack_trace:
            props["stackTrace"] = stack_trace
        return {"type": "a2ui.ErrorCard", "id": error_id, "props": props}

    # ------------------------------------------------------------------ #
    #  Message builders
    # ------------------------------------------------------------------ #

    @staticmethod
    def begin_rendering(components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Initial render message — sets all visible components."""
        return {
            "messageType": "beginRendering",
            "components": components,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def surface_update(components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Incremental UI update — adds or replaces components by id."""
        return {
            "messageType": "surfaceUpdate",
            "components": components,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def data_model_update(components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Data-only update — updates props without re-rendering structure."""
        return {
            "messageType": "dataModelUpdate",
            "components": components,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def state_snapshot(components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Full state snapshot for sync / reconnection."""
        return {
            "messageType": "stateSnapshot",
            "components": components,
            "timestamp": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------ #
    #  Convenience: emit as JSON string
    # ------------------------------------------------------------------ #

    @classmethod
    def emit(cls, message: Dict[str, Any]) -> str:
        """Serialize an A2UI message to JSON string."""
        return json.dumps(message, default=str)
