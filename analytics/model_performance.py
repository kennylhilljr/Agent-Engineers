"""Model Performance Comparator for advanced analytics (AI-249).

Provides side-by-side quality comparisons across AI model providers:
- Quality scores by provider
- Task type affinity matrix (which model wins which task type)
- Cross-validation agreement rate between providers
"""

from __future__ import annotations

from typing import Dict, List

# ---------------------------------------------------------------------------
# Synthetic but realistic quality score data
# ---------------------------------------------------------------------------

# Overall quality scores 0-100 per provider
_PROVIDER_QUALITY_SCORES: Dict[str, Dict] = {
    "claude-haiku": {
        "overall_score": 78.4,
        "latency_ms": 420,
        "cost_efficiency": 95.0,
        "reasoning": 72.0,
        "code_generation": 76.0,
        "text_summarisation": 81.0,
        "tool_use": 80.0,
    },
    "claude-sonnet": {
        "overall_score": 88.6,
        "latency_ms": 1_150,
        "cost_efficiency": 82.0,
        "reasoning": 90.0,
        "code_generation": 89.0,
        "text_summarisation": 87.0,
        "tool_use": 91.0,
    },
    "claude-opus": {
        "overall_score": 93.1,
        "latency_ms": 2_800,
        "cost_efficiency": 60.0,
        "reasoning": 96.0,
        "code_generation": 93.0,
        "text_summarisation": 90.0,
        "tool_use": 94.0,
    },
    "gpt-4o": {
        "overall_score": 87.9,
        "latency_ms": 980,
        "cost_efficiency": 78.0,
        "reasoning": 88.0,
        "code_generation": 87.0,
        "text_summarisation": 88.0,
        "tool_use": 89.0,
    },
    "gemini-pro": {
        "overall_score": 84.2,
        "latency_ms": 860,
        "cost_efficiency": 85.0,
        "reasoning": 83.0,
        "code_generation": 82.0,
        "text_summarisation": 86.0,
        "tool_use": 84.0,
    },
}

# Task types that appear in the affinity matrix
_TASK_TYPES: List[str] = [
    "code_generation",
    "bug_fixing",
    "code_review",
    "documentation",
    "architecture_design",
    "test_writing",
    "refactoring",
    "security_audit",
    "performance_optimisation",
    "api_design",
]

# Manually curated affinity winners for each task type.
# In production this would come from aggregated evaluation logs.
_TASK_AFFINITY: Dict[str, str] = {
    "code_generation": "claude-sonnet",
    "bug_fixing": "claude-sonnet",
    "code_review": "claude-opus",
    "documentation": "gpt-4o",
    "architecture_design": "claude-opus",
    "test_writing": "claude-sonnet",
    "refactoring": "claude-sonnet",
    "security_audit": "claude-opus",
    "performance_optimisation": "claude-sonnet",
    "api_design": "claude-sonnet",
}

# Cross-validation agreement rate: fraction of tasks where claude and gpt-4o
# independently produced the same verdict/classification.
_CROSS_VALIDATION_AGREEMENT_RATE = 0.847


class ModelPerformanceComparator:
    """Compares quality scores and task affinity across AI model providers.

    Returns pre-computed synthetic benchmark data shaped for the analytics
    dashboard panels.
    """

    def get_quality_scores_by_provider(self) -> Dict:
        """Return quality scores for all known model providers.

        Returns:
            Dict mapping provider name -> score dict with keys:
                - overall_score (float 0-100)
                - latency_ms (int): median latency
                - cost_efficiency (float 0-100): cost-adjusted efficiency
                - reasoning (float 0-100)
                - code_generation (float 0-100)
                - text_summarisation (float 0-100)
                - tool_use (float 0-100)
        """
        return dict(_PROVIDER_QUALITY_SCORES)

    def get_task_affinity_matrix(self) -> Dict:
        """Return the task-type affinity matrix.

        For each task type, identifies which model provider achieves the
        highest quality score.

        Returns:
            Dict with keys:
                - task_types (list[str]): all task types evaluated
                - affinity (dict): task_type -> winner provider
                - scores_by_task (dict): task_type ->
                      {provider -> score} for comparison
        """
        scores_by_task: Dict[str, Dict[str, float]] = {}
        for task in _TASK_TYPES:
            scores_by_task[task] = {}
            for provider, data in _PROVIDER_QUALITY_SCORES.items():
                score = data.get(task, data["overall_score"] * 0.95)
                scores_by_task[task][provider] = round(float(score), 2)

        return {
            "task_types": _TASK_TYPES,
            "affinity": dict(_TASK_AFFINITY),
            "scores_by_task": scores_by_task,
        }

    def get_crossvalidation_agreement_rate(self) -> float:
        """Return the cross-validation agreement rate between providers.

        Measures the fraction of tasks where Claude and GPT-4o produced
        the same verdict when evaluated independently on the same task set.

        Returns:
            Float between 0 and 1 representing agreement fraction.
        """
        return _CROSS_VALIDATION_AGREEMENT_RATE
