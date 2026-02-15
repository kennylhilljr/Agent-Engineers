"""CLI Agent Detail/Drill-Down View for Agent Status Monitoring.

Provides a detailed agent profile view showing level, XP, performance stats,
strengths/weaknesses, achievements, and recent events.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List

from rich.console import Console
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Level titles
LEVEL_TITLES = {
    1: "Intern",
    2: "Junior",
    3: "Mid-Level",
    4: "Senior",
    5: "Staff",
    6: "Principal",
    7: "Distinguished",
    8: "Fellow",
}


class AgentDetailRenderer:
    """Renders detailed agent profile view using rich components."""

    def __init__(self, console: Console):
        """Initialize the agent detail renderer.

        Args:
            console: Rich console instance for rendering
        """
        self.console = console

    def create_profile_panel(self, agent_data: Dict[str, Any], agent_name: str) -> Panel:
        """Create agent profile panel with basic information.

        Args:
            agent_data: Agent data dictionary from metrics
            agent_name: Name of the agent

        Returns:
            Rich Panel with agent profile information
        """
        text = Text()

        text.append(f"{agent_name}\n", style="bold cyan underline")

        xp = agent_data.get("xp", 0)
        level = agent_data.get("level", 1)
        level_title = LEVEL_TITLES.get(level, "Unknown")

        text.append("Experience (XP): ", style="bold")
        text.append(f"{xp} XP (Level {level} - {level_title})\n", style="cyan")

        text.append("Current Streak: ", style="bold")
        current_streak = agent_data.get("current_streak", 0)
        best_streak = agent_data.get("best_streak", 0)
        text.append(f"{current_streak} (Best: {best_streak})\n", style="yellow")

        return Panel(text, title="Agent Profile", border_style="cyan")

    def create_performance_panel(self, agent_data: Dict[str, Any]) -> Panel:
        """Create performance metrics panel.

        Args:
            agent_data: Agent data dictionary from metrics

        Returns:
            Rich Panel with performance statistics
        """
        text = Text()

        success_rate = agent_data.get("success_rate", 0.0)
        total_invocations = agent_data.get("total_invocations", 0)
        successful_invocations = agent_data.get("successful_invocations", 0)
        failed_invocations = agent_data.get("failed_invocations", 0)

        text.append("Success Rate: ", style="bold")
        if success_rate >= 0.9:
            style = "green"
        elif success_rate >= 0.7:
            style = "yellow"
        else:
            style = "red"
        text.append(f"{success_rate * 100:.1f}%\n", style=style)

        text.append("Invocations: ", style="bold")
        text.append(f"{successful_invocations} successful, {failed_invocations} failed (Total: {total_invocations})\n", style="cyan")

        text.append("Average Duration: ", style="bold")
        avg_duration = agent_data.get("avg_duration_seconds", 0.0)
        text.append(f"{self._format_duration(avg_duration)}\n", style="cyan")

        text.append("Tokens Per Call: ", style="bold")
        avg_tokens = agent_data.get("avg_tokens_per_call", 0.0)
        text.append(f"{avg_tokens:.0f} tokens\n", style="cyan")

        text.append("Cost Per Success: ", style="bold")
        cost = agent_data.get("cost_per_success_usd", 0.0)
        text.append(f"${cost:.4f}\n", style="cyan")

        total_tokens = agent_data.get("total_tokens", 0)
        total_cost = agent_data.get("total_cost_usd", 0.0)
        total_duration = agent_data.get("total_duration_seconds", 0.0)

        text.append("\nTotal Stats:\n", style="bold underline")
        text.append(f"  - Tokens: {total_tokens:,}\n", style="dim")
        text.append(f"  - Cost: ${total_cost:.4f}\n", style="dim")
        text.append(f"  - Duration: {self._format_duration(total_duration)}\n", style="dim")

        return Panel(text, title="Performance Metrics", border_style="magenta")

    def create_strengths_weaknesses_panel(self, agent_data: Dict[str, Any]) -> Panel:
        """Create strengths and weaknesses panel.

        Args:
            agent_data: Agent data dictionary from metrics

        Returns:
            Rich Panel with strengths and weaknesses
        """
        text = Text()

        strengths = agent_data.get("strengths", [])
        weaknesses = agent_data.get("weaknesses", [])

        text.append("Strengths:\n", style="bold green")
        if strengths:
            for strength in strengths:
                display_name = " ".join(word.capitalize() for word in strength.split("_"))
                text.append(f"  + {display_name}\n", style="green")
        else:
            text.append("  [dim]None identified[/dim]\n")

        text.append("\nWeaknesses:\n", style="bold red")
        if weaknesses:
            for weakness in weaknesses:
                display_name = " ".join(word.capitalize() for word in weakness.split("_"))
                text.append(f"  - {display_name}\n", style="red")
        else:
            text.append("  [dim]None identified[/dim]\n")

        return Panel(text, title="Strengths & Weaknesses", border_style="yellow")

    def create_achievements_panel(self, agent_data: Dict[str, Any]) -> Panel:
        """Create achievements panel.

        Args:
            agent_data: Agent data dictionary from metrics

        Returns:
            Rich Panel with achievements
        """
        text = Text()

        achievements = agent_data.get("achievements", [])

        if achievements:
            for achievement in achievements:
                display_name = " ".join(word.capitalize() for word in achievement.split("_"))
                text.append(f"  {display_name}\n", style="yellow")
        else:
            text.append("  [dim]No achievements earned yet[/dim]\n")

        text.append(f"\nTotal Achievements: {len(achievements)}", style="dim")

        return Panel(text, title="Achievements", border_style="yellow")

    def create_recent_events_table(self, events: List[Dict[str, Any]], agent_name: str, limit: int = 10) -> Table:
        """Create table of recent events for this agent.

        Args:
            events: List of all events from metrics
            agent_name: Name of agent to filter for
            limit: Maximum number of events to show

        Returns:
            Rich Table with recent events
        """
        table = Table(title=f"Recent Events ({agent_name})", show_header=True, header_style="bold magenta")
        table.add_column("Time", style="dim", width=20)
        table.add_column("Ticket", style="cyan", width=12)
        table.add_column("Status", style="white", width=10)
        table.add_column("Tokens", style="yellow", width=10)
        table.add_column("Duration", style="green", width=12)

        agent_events = [e for e in events if e.get("agent_name") == agent_name]
        agent_events = agent_events[-limit:] if len(agent_events) > limit else agent_events
        agent_events = list(reversed(agent_events))

        if not agent_events:
            table.add_row("No events", "N/A", "N/A", "N/A", "N/A")
            return table

        now = datetime.now(timezone.utc)
        for event in agent_events:
            started_at = event.get("started_at", "")
            if started_at:
                try:
                    event_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    time_ago = self._format_time_ago((now - event_dt).total_seconds())
                    time_str = time_ago
                except (ValueError, TypeError):
                    time_str = "Unknown"
            else:
                time_str = "Unknown"

            status = event.get("status", "unknown").upper()
            if status == "SUCCESS":
                status_str = f"[green]{status}[/green]"
            elif status == "ERROR":
                status_str = f"[red]{status}[/red]"
            else:
                status_str = f"[yellow]{status}[/yellow]"

            ticket = event.get("ticket_key", "N/A")
            tokens = event.get("total_tokens", 0)
            duration = event.get("duration_seconds", 0)

            table.add_row(
                time_str,
                ticket,
                status_str,
                f"{tokens:,}",
                f"{self._format_duration(duration)}"
            )

        return table

    def render_agent_detail(
        self,
        agent_name: str,
        agent_data: Dict[str, Any],
        state: Dict[str, Any]
    ) -> None:
        """Render and display complete agent detail view.

        Args:
            agent_name: Name of the agent
            agent_data: Agent data dictionary from metrics
            state: Complete metrics state dictionary
        """
        events = state.get("events", [])

        self.console.print()
        self.console.print(self.create_profile_panel(agent_data, agent_name))
        self.console.print()
        self.console.print(self.create_performance_panel(agent_data))
        self.console.print()

        strengths_panel = self.create_strengths_weaknesses_panel(agent_data)
        achievements_panel = self.create_achievements_panel(agent_data)
        self.console.print(Columns([strengths_panel, achievements_panel]))
        self.console.print()

        self.console.print(self.create_recent_events_table(events, agent_name))
        self.console.print()

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into human-readable duration string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            mins = int(seconds) // 60
            secs = int(seconds) % 60
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds) // 3600
            remaining = int(seconds) % 3600
            mins = remaining // 60
            return f"{hours}h {mins}m"

    @staticmethod
    def _format_time_ago(seconds: float) -> str:
        """Format seconds into human-readable 'time ago' string."""
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        else:
            return f"{int(seconds / 86400)}d ago"
