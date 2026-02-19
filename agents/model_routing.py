"""Model Routing for Agent Dashboard (AI-254).

Implements intelligent Opus model routing for high-complexity tasks where
deeper reasoning justifies the cost premium.

Routing Criteria:

PR Reviewer Agent - trigger Opus when:
  - Diff size > 500 lines changed
  - Files changed include: architecture/, core/, auth/, billing/, security/
  - PR contains database schema migrations
  - PR has more than 3 files with > 50% change ratio
  - Manual override: label ``review:opus`` on PR

Coding Agent - trigger Opus when:
  - Task description contains keywords: refactor, architecture, redesign, migration
  - Estimated complexity score > 8 (from PM Agent analysis)
  - Cross-cutting changes affecting 5+ modules
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Sensitive directory paths that trigger Opus routing for PR reviews
SENSITIVE_DIRECTORIES: frozenset[str] = frozenset(
    ["architecture", "core", "auth", "billing", "security"]
)

# Keywords in task descriptions that trigger Opus routing for the coding agent
OPUS_TASK_KEYWORDS: tuple[str, ...] = (
    "refactor",
    "architecture",
    "redesign",
    "migration",
)

# Minimum complexity score to trigger Opus for the coding agent
OPUS_COMPLEXITY_THRESHOLD = 8

# PR diff line threshold for Opus routing
PR_DIFF_LINE_THRESHOLD = 500

# Number of high-change-ratio files needed to trigger Opus
HIGH_CHANGE_RATIO_FILE_THRESHOLD = 3

# Migration-related file path patterns (lower-cased for comparison)
MIGRATION_FILE_PATTERNS: tuple[str, ...] = (
    "migration",
    "migrations",
    "schema",
    "alembic",
    "flyway",
)

# Manual override label
OPUS_OVERRIDE_LABEL = "review:opus"

# Default cost cap per agent run (USD)
DEFAULT_COST_CAP_USD = 5.00

# Alert threshold as a fraction of the cost cap
COST_CAP_ALERT_FRACTION = 0.80

# Cross-cutting module threshold for coding agent
CROSS_CUTTING_MODULE_THRESHOLD = 5


# ---------------------------------------------------------------------------
# ModelTier enum
# ---------------------------------------------------------------------------


class ModelTier(Enum):
    """Available Claude model tiers in ascending capability/cost order."""

    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"

    def __str__(self) -> str:  # pragma: no cover
        return self.value


# ---------------------------------------------------------------------------
# Complexity scorer
# ---------------------------------------------------------------------------


def estimate_complexity(task: dict) -> int:
    """Estimate the complexity of a task on a 1-10 scale.

    Examines the task description, keyword signals, module count, and any
    pre-computed complexity hints to produce an integer score.

    Args:
        task: Dictionary describing the task.  Recognised keys:
            - ``description`` (str): Free-text task description.
            - ``keywords`` (list[str]): Explicit keyword tags.
            - ``modules_affected`` (int | list): Number of modules touched.
            - ``complexity_hint`` (int): Pre-computed hint from PM Agent (0-10).
            - ``lines_changed`` (int): Estimated lines changed.
            - ``files_changed`` (int): Number of files changed.

    Returns:
        Integer score between 1 and 10 (inclusive) where 10 is maximally
        complex.
    """
    score = 1

    description: str = (task.get("description") or "").lower()
    keywords: List[str] = [k.lower() for k in (task.get("keywords") or [])]

    # Score from keyword presence
    high_complexity_words = {
        "refactor": 3,
        "architecture": 3,
        "redesign": 3,
        "migration": 3,
        "security": 2,
        "auth": 2,
        "billing": 2,
        "core": 1,
        "integration": 1,
        "performance": 1,
        "database": 2,
        "schema": 2,
    }
    for word, bonus in high_complexity_words.items():
        if word in description or word in keywords:
            score += bonus

    # Score from modules affected
    modules_affected = task.get("modules_affected", 0)
    if isinstance(modules_affected, list):
        modules_affected = len(modules_affected)
    if modules_affected >= CROSS_CUTTING_MODULE_THRESHOLD:
        score += 3
    elif modules_affected >= 3:
        score += 1

    # Score from lines changed
    lines_changed = int(task.get("lines_changed") or 0)
    if lines_changed > PR_DIFF_LINE_THRESHOLD:
        score += 2
    elif lines_changed > 200:
        score += 1

    # Score from number of files changed
    files_changed = int(task.get("files_changed") or 0)
    if files_changed > 10:
        score += 1

    # Honour an explicit PM Agent complexity hint (clamp to 1-10)
    hint = task.get("complexity_hint")
    if hint is not None:
        try:
            hint_int = int(hint)
            # Blend: take the max of computed and hinted score
            score = max(score, hint_int)
        except (TypeError, ValueError):
            pass

    # Clamp to [1, 10]
    return max(1, min(10, score))


# ---------------------------------------------------------------------------
# Model selector
# ---------------------------------------------------------------------------


def select_model(
    agent_type: str,
    complexity: int,
    pr_metadata: Optional[Dict] = None,
) -> ModelTier:
    """Select the appropriate model tier for an agent and task.

    For the *pr_reviewer* agent the following conditions each individually
    trigger Opus:
      - Diff size > 500 lines
      - Any changed file path under a sensitive directory
      - Any file path matching migration patterns
      - More than 3 files with change ratio > 50 %
      - Label ``review:opus`` present

    For the *coding* agent Opus is triggered when:
      - Task description contains OPUS_TASK_KEYWORDS
      - Complexity score > OPUS_COMPLEXITY_THRESHOLD (8)
      - Cross-cutting changes affecting 5+ modules

    All other agents default to Sonnet.

    Args:
        agent_type: The agent type string (e.g. ``"pr_reviewer"``,
            ``"coding"``).
        complexity: Integer complexity score from ``estimate_complexity()``.
        pr_metadata: Optional dict with PR / task context.  Recognised keys
            for PR reviewers:
            - ``lines_changed`` (int): Total diff lines.
            - ``files_changed`` (list[str]): Changed file paths.
            - ``labels`` (list[str]): PR labels.
            - ``file_change_ratios`` (dict[str, float]): Per-file change ratio
              (0-1 or 0-100).
            For coding agents:
            - ``description`` (str): Task description text.
            - ``modules_affected`` (int | list): Modules touched.

    Returns:
        The recommended :class:`ModelTier`.
    """
    pr_metadata = pr_metadata or {}
    agent_lower = agent_type.lower()

    if agent_lower == "pr_reviewer":
        return _select_model_for_pr_reviewer(pr_metadata)
    elif agent_lower == "coding":
        return _select_model_for_coding(complexity, pr_metadata)
    else:
        # All other agents default to SONNET unless complexity pushes to OPUS
        if complexity > OPUS_COMPLEXITY_THRESHOLD:
            return ModelTier.OPUS
        return ModelTier.SONNET


def _select_model_for_pr_reviewer(pr_metadata: Dict) -> ModelTier:
    """Evaluate PR-specific routing criteria and return the model tier."""
    lines_changed: int = int(pr_metadata.get("lines_changed") or 0)
    files_changed: List[str] = list(pr_metadata.get("files_changed") or [])
    labels: List[str] = [lbl.lower() for lbl in (pr_metadata.get("labels") or [])]
    file_change_ratios: Dict[str, float] = dict(
        pr_metadata.get("file_change_ratios") or {}
    )

    # 1. Manual override label
    if OPUS_OVERRIDE_LABEL in labels:
        logger.debug("Opus selected: manual override label '%s'", OPUS_OVERRIDE_LABEL)
        return ModelTier.OPUS

    # 2. Diff size > 500 lines
    if lines_changed > PR_DIFF_LINE_THRESHOLD:
        logger.debug("Opus selected: diff size %d > %d", lines_changed, PR_DIFF_LINE_THRESHOLD)
        return ModelTier.OPUS

    # 3. Sensitive directories
    for file_path in files_changed:
        path_lower = file_path.lower().replace("\\", "/")
        for sensitive_dir in SENSITIVE_DIRECTORIES:
            if f"/{sensitive_dir}/" in path_lower or path_lower.startswith(f"{sensitive_dir}/"):
                logger.debug(
                    "Opus selected: file '%s' under sensitive directory '%s'",
                    file_path,
                    sensitive_dir,
                )
                return ModelTier.OPUS

    # 4. Database schema migrations
    for file_path in files_changed:
        path_lower = file_path.lower()
        for pattern in MIGRATION_FILE_PATTERNS:
            if pattern in path_lower:
                logger.debug(
                    "Opus selected: migration file detected '%s'", file_path
                )
                return ModelTier.OPUS

    # 5. More than HIGH_CHANGE_RATIO_FILE_THRESHOLD files with > 50% change ratio
    high_change_count = 0
    for file_path, ratio in file_change_ratios.items():
        # Accept ratio expressed as 0-1 or 0-100
        normalised = ratio if ratio <= 1.0 else ratio / 100.0
        if normalised > 0.50:
            high_change_count += 1
    if high_change_count > HIGH_CHANGE_RATIO_FILE_THRESHOLD:
        logger.debug(
            "Opus selected: %d files with >50%% change ratio", high_change_count
        )
        return ModelTier.OPUS

    return ModelTier.SONNET


def _select_model_for_coding(complexity: int, task_metadata: Dict) -> ModelTier:
    """Evaluate coding-agent-specific routing criteria and return the model tier."""
    description: str = (task_metadata.get("description") or "").lower()

    # 1. Keywords in task description
    for keyword in OPUS_TASK_KEYWORDS:
        if keyword in description:
            logger.debug("Opus selected: keyword '%s' in task description", keyword)
            return ModelTier.OPUS

    # 2. Complexity score > threshold
    if complexity > OPUS_COMPLEXITY_THRESHOLD:
        logger.debug(
            "Opus selected: complexity score %d > threshold %d",
            complexity,
            OPUS_COMPLEXITY_THRESHOLD,
        )
        return ModelTier.OPUS

    # 3. Cross-cutting changes affecting 5+ modules
    modules_affected = task_metadata.get("modules_affected", 0)
    if isinstance(modules_affected, list):
        modules_affected = len(modules_affected)
    if int(modules_affected) >= CROSS_CUTTING_MODULE_THRESHOLD:
        logger.debug(
            "Opus selected: %d modules affected (>= %d)",
            modules_affected,
            CROSS_CUTTING_MODULE_THRESHOLD,
        )
        return ModelTier.OPUS

    return ModelTier.SONNET


# ---------------------------------------------------------------------------
# CostTracker
# ---------------------------------------------------------------------------


@dataclass
class CostTracker:
    """Per-run cost tracker with configurable cap and 80% alert threshold.

    Usage::

        tracker = CostTracker(cap_usd=5.00)
        tracker.add(0.40, model_tier=ModelTier.OPUS)
        if tracker.is_alert_threshold_exceeded:
            notify(...)
        if not tracker.is_within_cap:
            raise CostCapExceededError(...)

    Attributes:
        cap_usd: Maximum allowed spend per agent run (USD).
        alert_fraction: Fraction of ``cap_usd`` that triggers an alert
            (default 0.80).
        cost_by_tier: Accumulated cost breakdown by :class:`ModelTier`.
        total_cost_usd: Sum of all recorded costs.
        alert_fired: True once the 80%-of-cap threshold has been crossed.
    """

    cap_usd: float = DEFAULT_COST_CAP_USD
    alert_fraction: float = COST_CAP_ALERT_FRACTION
    cost_by_tier: Dict[ModelTier, float] = field(default_factory=dict)
    total_cost_usd: float = 0.0
    alert_fired: bool = False

    def __post_init__(self) -> None:
        # Initialise cost bucket for each tier
        for tier in ModelTier:
            if tier not in self.cost_by_tier:
                self.cost_by_tier[tier] = 0.0

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, cost_usd: float, model_tier: ModelTier = ModelTier.SONNET) -> None:
        """Record an incremental cost charge.

        Args:
            cost_usd: Cost in USD to add to this run's total.
            model_tier: The model tier that incurred the cost.
        """
        if cost_usd < 0:
            raise ValueError(f"cost_usd must be non-negative, got {cost_usd}")

        self.cost_by_tier[model_tier] = self.cost_by_tier.get(model_tier, 0.0) + cost_usd
        self.total_cost_usd += cost_usd

        # Fire alert exactly once when crossing the alert threshold
        if not self.alert_fired and self.total_cost_usd >= self.alert_threshold_usd:
            self.alert_fired = True
            logger.warning(
                "Cost alert: run cost $%.4f has reached %.0f%% of cap ($%.2f).",
                self.total_cost_usd,
                self.alert_fraction * 100,
                self.cap_usd,
            )

    def reset(self) -> None:
        """Reset all cost counters (start a new run)."""
        for tier in ModelTier:
            self.cost_by_tier[tier] = 0.0
        self.total_cost_usd = 0.0
        self.alert_fired = False

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def alert_threshold_usd(self) -> float:
        """USD value at which the cost alert fires."""
        return self.cap_usd * self.alert_fraction

    @property
    def is_alert_threshold_exceeded(self) -> bool:
        """True when total cost has reached the 80% alert threshold."""
        return self.total_cost_usd >= self.alert_threshold_usd

    @property
    def is_within_cap(self) -> bool:
        """True when total cost is still below the hard cap."""
        return self.total_cost_usd < self.cap_usd

    @property
    def remaining_budget_usd(self) -> float:
        """Remaining spend budget for this run."""
        return max(0.0, self.cap_usd - self.total_cost_usd)

    def summary(self) -> Dict:
        """Return a JSON-serialisable summary of this run's costs.

        Returns:
            dict with keys: ``total_cost_usd``, ``cap_usd``,
            ``remaining_budget_usd``, ``alert_fired``,
            ``is_within_cap``, ``cost_by_tier``.
        """
        return {
            "total_cost_usd": round(self.total_cost_usd, 6),
            "cap_usd": self.cap_usd,
            "remaining_budget_usd": round(self.remaining_budget_usd, 6),
            "alert_fired": self.alert_fired,
            "is_within_cap": self.is_within_cap,
            "alert_threshold_usd": round(self.alert_threshold_usd, 6),
            "cost_by_tier": {
                tier.value: round(cost, 6)
                for tier, cost in self.cost_by_tier.items()
            },
        }


# ---------------------------------------------------------------------------
# Convenience function for the orchestrator
# ---------------------------------------------------------------------------


def check_cost_cap(current_cost: float, cap: float) -> bool:
    """Check whether ``current_cost`` is within the given ``cap``.

    Logs a warning when 80 % of the cap is reached or exceeded.

    Args:
        current_cost: The current accumulated cost in USD.
        cap: The maximum allowed cost in USD.

    Returns:
        ``True`` if ``current_cost`` is strictly below ``cap``
        (the run may continue); ``False`` if the cap has been hit.
    """
    if cap <= 0:
        raise ValueError(f"cap must be positive, got {cap}")

    alert_threshold = cap * COST_CAP_ALERT_FRACTION
    if current_cost >= alert_threshold:
        logger.warning(
            "Cost alert: current cost $%.4f is >= %.0f%% of cap ($%.2f).",
            current_cost,
            COST_CAP_ALERT_FRACTION * 100,
            cap,
        )

    return current_cost < cap


# ---------------------------------------------------------------------------
# Org-level configurable cost cap
# ---------------------------------------------------------------------------


def get_cost_cap_for_org(org_id: Optional[str] = None) -> float:
    """Return the cost cap for the given organisation.

    Reads ``AGENT_COST_CAP_USD`` from the environment; falls back to
    ``DEFAULT_COST_CAP_USD`` ($5.00) when not set.

    Args:
        org_id: Unused for now — reserved for per-org overrides loaded from
            a database or config file in future iterations.

    Returns:
        Cost cap in USD as a float.
    """
    env_cap = os.environ.get("AGENT_COST_CAP_USD", "")
    if env_cap.strip():
        try:
            return float(env_cap)
        except ValueError:
            logger.warning(
                "Invalid AGENT_COST_CAP_USD='%s', using default $%.2f",
                env_cap,
                DEFAULT_COST_CAP_USD,
            )
    return DEFAULT_COST_CAP_USD
