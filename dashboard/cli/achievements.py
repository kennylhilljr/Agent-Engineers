"""CLI Achievement Display for Agent Status Dashboard.

Displays agent achievements with emoji icons, unlock status, descriptions,
and progress indicators. Supports 12 achievement types.
"""

from typing import Dict

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

# Achievement definitions with emoji icons and descriptions
ACHIEVEMENT_ICONS = {
    "first_blood": "🩸",
    "century_club": "💯",
    "perfect_day": "✨",
    "speed_demon": "⚡",
    "comeback_kid": "🔥",
    "big_spender": "💰",
    "penny_pincher": "🪙",
    "marathon": "🏃",
    "polyglot": "🌍",
    "night_owl": "🌙",
    "streak_10": "🔥",
    "streak_25": "⭐",
}

ACHIEVEMENT_NAMES = {
    "first_blood": "First Blood",
    "century_club": "Century Club",
    "perfect_day": "Perfect Day",
    "speed_demon": "Speed Demon",
    "comeback_kid": "Comeback Kid",
    "big_spender": "Big Spender",
    "penny_pincher": "Penny Pincher",
    "marathon": "Marathon Runner",
    "polyglot": "Polyglot",
    "night_owl": "Night Owl",
    "streak_10": "On Fire",
    "streak_25": "Unstoppable",
}

ACHIEVEMENT_DESCRIPTIONS = {
    "first_blood": "First successful invocation",
    "century_club": "100 successful invocations",
    "perfect_day": "10+ invocations in one session, 0 errors",
    "speed_demon": "5 consecutive completions under 30s",
    "comeback_kid": "Success immediately after 3+ consecutive errors",
    "big_spender": "Single invocation over $1.00",
    "penny_pincher": "50+ successes at < $0.01 each",
    "marathon": "100+ invocations in a single project",
    "polyglot": "Agent used across 5+ different ticket types",
    "night_owl": "Invocation between 00:00-05:00 local time",
    "streak_10": "10 consecutive successes",
    "streak_25": "25 consecutive successes",
}


class AchievementRenderer:
    """Renders achievement displays using rich components."""

    def __init__(self, console: Console):
        """Initialize the achievement renderer.

        Args:
            console: Rich console instance for rendering
        """
        self.console = console

    def create_achievements_grid(self, agent_name: str, agent_data: Dict) -> Panel:
        """Create a grid display of all achievements for an agent.

        Args:
            agent_name: Name of the agent
            agent_data: Agent data dictionary from metrics

        Returns:
            Rich Panel with achievement grid display
        """
        achievements = agent_data.get("achievements", [])
        total_xp = agent_data.get("xp", 0)

        text = Text()
        text.append(f"Agent: ", style="bold")
        text.append(f"{agent_name}\n", style="cyan bold")
        text.append(f"XP: ", style="bold")
        text.append(f"{total_xp}\n", style="yellow bold")
        text.append("\n", style="")

        all_achievement_ids = list(ACHIEVEMENT_ICONS.keys())

        unlocked = sorted([a for a in achievements if a in ACHIEVEMENT_ICONS])
        locked = sorted([a for a in all_achievement_ids if a not in unlocked])

        if unlocked:
            text.append("Unlocked Achievements\n", style="bold green")
            text.append("=" * 50 + "\n", style="dim green")
            for achievement_id in unlocked:
                icon = ACHIEVEMENT_ICONS[achievement_id]
                name = ACHIEVEMENT_NAMES[achievement_id]
                description = ACHIEVEMENT_DESCRIPTIONS[achievement_id]
                text.append(f"{icon} ", style="")
                text.append(f"{name}\n", style="bold yellow")
                text.append(f"   {description}\n", style="dim")
            text.append("\n", style="")
        else:
            text.append("No achievements unlocked yet.\n", style="dim yellow")
            text.append("\n", style="")

        if locked:
            text.append("Locked Achievements\n", style="bold dim")
            text.append("=" * 50 + "\n", style="dim")
            for achievement_id in locked:
                name = ACHIEVEMENT_NAMES[achievement_id]
                description = ACHIEVEMENT_DESCRIPTIONS[achievement_id]
                text.append(f"🔒 ", style="dim")
                text.append(f"{name}\n", style="dim")
                text.append(f"   {description}\n", style="dim")
            text.append("\n", style="")

        text.append("Summary\n", style="bold cyan")
        text.append("=" * 50 + "\n", style="dim cyan")
        text.append(f"Unlocked: {len(unlocked)}/12\n", style="green")
        text.append(f"Progress: ", style="")
        progress_bar = self._create_progress_bar(len(unlocked), 12)
        text.append(f"{progress_bar}\n", style="cyan")

        return Panel(text, title=f"Achievements - {agent_name}", border_style="cyan")

    def create_all_agents_achievements(self, agents: Dict[str, Dict]) -> Panel:
        """Create achievement summary for all agents.

        Args:
            agents: Dictionary of all agent data

        Returns:
            Rich Panel with all agents' achievements
        """
        text = Text()
        text.append("Agent Achievement Summary\n", style="bold cyan")
        text.append("=" * 60 + "\n\n", style="dim cyan")

        agent_list = [
            (name, data.get("achievements", []), data.get("xp", 0))
            for name, data in agents.items()
        ]
        agent_list.sort(key=lambda x: len(x[1]), reverse=True)

        for agent_name, achievements, xp in agent_list:
            unlocked = len([a for a in achievements if a in ACHIEVEMENT_ICONS])
            progress_bar = self._create_progress_bar(unlocked, 12)

            text.append(f"{agent_name:<15} ", style="cyan bold")
            text.append(f"[XP: {xp:<4}] ", style="yellow")
            text.append(f"{progress_bar} ", style="cyan")
            text.append(f"({unlocked}/12)\n", style="green")

            if achievements:
                recent = sorted(achievements)[-3:]
                for ach in recent:
                    icon = ACHIEVEMENT_ICONS.get(ach, "")
                    name = ACHIEVEMENT_NAMES.get(ach, ach)
                    text.append(f"  {icon} {name}\n", style="dim yellow")

        return Panel(text, title="All Agents", border_style="cyan")

    def create_initializing_layout(self) -> Layout:
        """Create layout for initializing state when metrics file doesn't exist.

        Returns:
            Rich Layout showing initializing state
        """
        layout = Layout()

        text = Text()
        text.append("\n\n", style="")
        text.append("Initializing Achievement View...\n\n", style="bold yellow")
        text.append("Waiting for metrics file to be created.\n", style="dim")
        text.append("Achievements will be displayed once agents start working.\n", style="dim")

        panel = Panel(text, title="Achievement View", border_style="yellow")
        layout.update(panel)

        return layout

    @staticmethod
    def _create_progress_bar(current: int, total: int, width: int = 20) -> str:
        """Create a visual progress bar.

        Args:
            current: Current progress value
            total: Total value
            width: Width of the progress bar

        Returns:
            ASCII progress bar string
        """
        filled = int((current / total) * width) if total > 0 else 0
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
