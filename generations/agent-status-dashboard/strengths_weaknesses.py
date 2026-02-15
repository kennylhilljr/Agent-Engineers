"""Strengths and weaknesses detection for agent profiling.

This module provides functions to automatically detect agent strengths and weaknesses
based on rolling window statistics. These insights help identify performance
characteristics across agents in the dashboard.

Strengths (positive attributes):
- fast_execution: Agent completes tasks significantly faster than average
- high_success_rate: Agent has very high success rate (>= 0.95)
- low_cost: Agent operates at lower cost than average
- consistent: Agent has low variance in performance
- prolific: Agent produces high volume of artifacts

Weaknesses (areas for improvement):
- high_error_rate: Agent fails frequently (success rate < 0.70)
- slow: Agent is significantly slower than average
- expensive: Agent costs significantly more than average
- inconsistent: Agent has high variance in performance

All functions are pure with no side effects, making them deterministic and testable.
"""

from typing import List, Tuple
from metrics import AgentEvent, AgentProfile, DashboardState


def calculate_rolling_window_stats(
    events: List[AgentEvent],
    agent_name: str,
    window_size: int = 20
) -> dict:
    """Calculate statistics for an agent over a rolling window of recent events.

    Args:
        events: List of all agent events (chronological order)
        agent_name: Name of the agent to analyze
        window_size: Number of recent events to analyze (default 20)

    Returns:
        Dictionary with rolling window statistics:
        - event_count: Number of events in window
        - success_rate: Ratio of successful events
        - avg_duration: Average duration in seconds
        - avg_cost: Average cost in USD
        - avg_tokens: Average total tokens
        - duration_variance: Variance in duration
        - artifact_count: Total artifacts produced

    Examples:
        >>> events = [...]  # List of events
        >>> stats = calculate_rolling_window_stats(events, "coding", window_size=10)
        >>> stats["success_rate"]
        0.9
    """
    # Filter events for this agent (most recent first, then reverse for chronological)
    agent_events = [e for e in events if e["agent_name"] == agent_name]

    # Take last N events (rolling window)
    window_events = agent_events[-window_size:] if len(agent_events) > window_size else agent_events

    if not window_events:
        return {
            "event_count": 0,
            "success_rate": 0.0,
            "avg_duration": 0.0,
            "avg_cost": 0.0,
            "avg_tokens": 0.0,
            "duration_variance": 0.0,
            "artifact_count": 0,
        }

    # Calculate statistics
    event_count = len(window_events)
    successful_count = sum(1 for e in window_events if e["status"] == "success")
    success_rate = successful_count / event_count if event_count > 0 else 0.0

    total_duration = sum(e["duration_seconds"] for e in window_events)
    avg_duration = total_duration / event_count if event_count > 0 else 0.0

    total_cost = sum(e["estimated_cost_usd"] for e in window_events)
    avg_cost = total_cost / event_count if event_count > 0 else 0.0

    total_tokens = sum(e["total_tokens"] for e in window_events)
    avg_tokens = total_tokens / event_count if event_count > 0 else 0.0

    # Calculate variance in duration
    if event_count > 1:
        durations = [e["duration_seconds"] for e in window_events]
        mean_duration = avg_duration
        variance = sum((d - mean_duration) ** 2 for d in durations) / event_count
        duration_variance = variance
    else:
        duration_variance = 0.0

    # Count artifacts
    artifact_count = sum(len(e["artifacts"]) for e in window_events)

    return {
        "event_count": event_count,
        "success_rate": success_rate,
        "avg_duration": avg_duration,
        "avg_cost": avg_cost,
        "avg_tokens": avg_tokens,
        "duration_variance": duration_variance,
        "artifact_count": artifact_count,
    }


def calculate_agent_percentiles(
    state: DashboardState,
    window_size: int = 20
) -> dict:
    """Calculate percentile rankings for each metric across all agents.

    Args:
        state: Dashboard state with all agents and events
        window_size: Size of rolling window for statistics

    Returns:
        Dictionary mapping agent_name to their percentile stats:
        - duration_percentile: 0.0 (slowest) to 1.0 (fastest)
        - cost_percentile: 0.0 (most expensive) to 1.0 (cheapest)
        - success_percentile: 0.0 (lowest) to 1.0 (highest)
        - consistency_percentile: 0.0 (least consistent) to 1.0 (most consistent)

    Examples:
        >>> percentiles = calculate_agent_percentiles(state)
        >>> percentiles["coding"]["duration_percentile"]
        0.75
    """
    if not state["agents"]:
        return {}

    # Get rolling window stats for all agents
    agent_stats = {}
    for agent_name in state["agents"].keys():
        agent_stats[agent_name] = calculate_rolling_window_stats(
            state["events"],
            agent_name,
            window_size
        )

    # Filter out agents with no events
    active_agents = {
        name: stats for name, stats in agent_stats.items()
        if stats["event_count"] > 0
    }

    if not active_agents:
        return {}

    # Calculate percentiles for each metric
    percentiles = {}

    for agent_name in active_agents.keys():
        stats = active_agents[agent_name]

        # Duration percentile (lower is better, so invert)
        all_durations = [s["avg_duration"] for s in active_agents.values()]
        if len(all_durations) > 1:
            sorted_durations = sorted(all_durations)
            rank = sorted_durations.index(stats["avg_duration"])
            duration_percentile = 1.0 - (rank / (len(sorted_durations) - 1))
        else:
            duration_percentile = 0.5

        # Cost percentile (lower is better, so invert)
        all_costs = [s["avg_cost"] for s in active_agents.values()]
        if len(all_costs) > 1:
            sorted_costs = sorted(all_costs)
            rank = sorted_costs.index(stats["avg_cost"])
            cost_percentile = 1.0 - (rank / (len(sorted_costs) - 1))
        else:
            cost_percentile = 0.5

        # Success percentile (higher is better)
        all_success_rates = [s["success_rate"] for s in active_agents.values()]
        if len(all_success_rates) > 1:
            sorted_success = sorted(all_success_rates)
            rank = sorted_success.index(stats["success_rate"])
            success_percentile = rank / (len(sorted_success) - 1)
        else:
            success_percentile = 0.5

        # Consistency percentile (lower variance is better, so invert)
        all_variances = [s["duration_variance"] for s in active_agents.values()]
        if len(all_variances) > 1:
            sorted_variances = sorted(all_variances)
            rank = sorted_variances.index(stats["duration_variance"])
            consistency_percentile = 1.0 - (rank / (len(sorted_variances) - 1))
        else:
            consistency_percentile = 0.5

        percentiles[agent_name] = {
            "duration_percentile": duration_percentile,
            "cost_percentile": cost_percentile,
            "success_percentile": success_percentile,
            "consistency_percentile": consistency_percentile,
        }

    return percentiles


def detect_strengths(
    agent_name: str,
    stats: dict,
    percentiles: dict,
    min_events: int = 5
) -> List[str]:
    """Detect strengths for an agent based on rolling window statistics.

    Strengths are detected when an agent exceeds certain thresholds:
    - fast_execution: duration_percentile >= 0.75 (top 25% fastest)
    - high_success_rate: success_rate >= 0.95
    - low_cost: cost_percentile >= 0.75 (top 25% cheapest)
    - consistent: consistency_percentile >= 0.75 (top 25% most consistent)
    - prolific: artifact_count > avg * 1.5

    Args:
        agent_name: Name of the agent
        stats: Rolling window statistics for the agent
        percentiles: Percentile rankings for all agents
        min_events: Minimum events required to detect strengths (default 5)

    Returns:
        List of strength identifiers

    Examples:
        >>> strengths = detect_strengths("coding", stats, percentiles)
        >>> "fast_execution" in strengths
        True
    """
    strengths = []

    # Need minimum events for reliable detection
    if stats["event_count"] < min_events:
        return strengths

    # Fast execution: top 25% fastest
    if (agent_name in percentiles and
        "duration_percentile" in percentiles[agent_name] and
        percentiles[agent_name]["duration_percentile"] >= 0.75):
        strengths.append("fast_execution")

    # High success rate: >= 95%
    if stats["success_rate"] >= 0.95:
        strengths.append("high_success_rate")

    # Low cost: top 25% cheapest
    if (agent_name in percentiles and
        "cost_percentile" in percentiles[agent_name] and
        percentiles[agent_name]["cost_percentile"] >= 0.75):
        strengths.append("low_cost")

    # Consistent: top 25% most consistent
    if (agent_name in percentiles and
        "consistency_percentile" in percentiles[agent_name] and
        percentiles[agent_name]["consistency_percentile"] >= 0.75):
        strengths.append("consistent")

    # Prolific: produces lots of artifacts
    # This is relative to event count - more than 2 artifacts per event on average
    if stats["event_count"] > 0 and stats["artifact_count"] / stats["event_count"] >= 2.0:
        strengths.append("prolific")

    return strengths


def detect_weaknesses(
    agent_name: str,
    stats: dict,
    percentiles: dict,
    min_events: int = 5
) -> List[str]:
    """Detect weaknesses for an agent based on rolling window statistics.

    Weaknesses are detected when an agent falls below certain thresholds:
    - high_error_rate: success_rate < 0.70
    - slow: duration_percentile <= 0.25 (bottom 25% slowest)
    - expensive: cost_percentile <= 0.25 (bottom 25% most expensive)
    - inconsistent: consistency_percentile <= 0.25 (bottom 25% most variable)

    Args:
        agent_name: Name of the agent
        stats: Rolling window statistics for the agent
        percentiles: Percentile rankings for all agents
        min_events: Minimum events required to detect weaknesses (default 5)

    Returns:
        List of weakness identifiers

    Examples:
        >>> weaknesses = detect_weaknesses("slow_agent", stats, percentiles)
        >>> "slow" in weaknesses
        True
    """
    weaknesses = []

    # Need minimum events for reliable detection
    if stats["event_count"] < min_events:
        return weaknesses

    # High error rate: < 70% success rate
    if stats["success_rate"] < 0.70:
        weaknesses.append("high_error_rate")

    # Slow: bottom 25% slowest
    if (agent_name in percentiles and
        "duration_percentile" in percentiles[agent_name] and
        percentiles[agent_name]["duration_percentile"] <= 0.25):
        weaknesses.append("slow")

    # Expensive: bottom 25% most expensive
    if (agent_name in percentiles and
        "cost_percentile" in percentiles[agent_name] and
        percentiles[agent_name]["cost_percentile"] <= 0.25):
        weaknesses.append("expensive")

    # Inconsistent: bottom 25% most variable
    if (agent_name in percentiles and
        "consistency_percentile" in percentiles[agent_name] and
        percentiles[agent_name]["consistency_percentile"] <= 0.25):
        weaknesses.append("inconsistent")

    return weaknesses


def update_agent_strengths_weaknesses(
    state: DashboardState,
    window_size: int = 20,
    min_events: int = 5
) -> DashboardState:
    """Update strengths and weaknesses for all agents in the dashboard state.

    This is the main function to call when updating agent profiles with
    auto-detected strengths and weaknesses based on rolling window statistics.

    Args:
        state: Dashboard state with all agents and events
        window_size: Size of rolling window for statistics (default 20)
        min_events: Minimum events required for detection (default 5)

    Returns:
        Updated dashboard state with strengths/weaknesses populated

    Examples:
        >>> state = update_agent_strengths_weaknesses(state)
        >>> state["agents"]["coding"]["strengths"]
        ['fast_execution', 'high_success_rate']
    """
    # Calculate percentiles across all agents
    percentiles = calculate_agent_percentiles(state, window_size)

    # Update each agent
    for agent_name, profile in state["agents"].items():
        # Get rolling window stats
        stats = calculate_rolling_window_stats(
            state["events"],
            agent_name,
            window_size
        )

        # Detect strengths and weaknesses
        strengths = detect_strengths(agent_name, stats, percentiles, min_events)
        weaknesses = detect_weaknesses(agent_name, stats, percentiles, min_events)

        # Update profile
        profile["strengths"] = strengths
        profile["weaknesses"] = weaknesses

    return state


def get_strength_description(strength: str) -> str:
    """Get human-readable description for a strength.

    Args:
        strength: Strength identifier

    Returns:
        Description string

    Examples:
        >>> get_strength_description("fast_execution")
        'Completes tasks significantly faster than average'
    """
    descriptions = {
        "fast_execution": "Completes tasks significantly faster than average",
        "high_success_rate": "Maintains very high success rate (>= 95%)",
        "low_cost": "Operates at lower cost than average",
        "consistent": "Demonstrates consistent performance with low variance",
        "prolific": "Produces high volume of artifacts",
    }

    return descriptions.get(strength, "Unknown strength")


def get_weakness_description(weakness: str) -> str:
    """Get human-readable description for a weakness.

    Args:
        weakness: Weakness identifier

    Returns:
        Description string

    Examples:
        >>> get_weakness_description("slow")
        'Significantly slower than average'
    """
    descriptions = {
        "high_error_rate": "Fails frequently (success rate < 70%)",
        "slow": "Significantly slower than average",
        "expensive": "Costs significantly more than average",
        "inconsistent": "Shows high variance in performance",
    }

    return descriptions.get(weakness, "Unknown weakness")
