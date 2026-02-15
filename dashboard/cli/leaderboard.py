"""CLI Leaderboard View for Agent Status Dashboard.

Displays agents sorted by XP with performance metrics including level,
success rate, average time, and cost per success.
"""

from datetime import datetime, timezone

from rich.console import Console
from rich.layout import Layout
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


class LeaderboardRenderer:
    """Renders the agent leaderboard using rich components."""

    def __init__(self, console: Console):
        """Initialize the leaderboard renderer.

        Args:
            console: Rich console instance for rendering
        """
        self.console = console

    def create_leaderboard_table(self, agents: dict) -> Table:
        """Create leaderboard table sorted by XP with all agent stats.

        Args:
            agents: Dictionary of agent profiles from DashboardState

        Returns:
            Rich Table with agents sorted by XP descending
        """
        table = Table(
            title="Agent Leaderboard (Sorted by XP)",
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Rank", style="cyan", width=6)
        table.add_column("Agent", style="cyan", width=15)
        table.add_column("XP", style="yellow", width=8, justify="right")
        table.add_column("Level", style="green", width=12)
        table.add_column("Success Rate", style="blue", width=14, justify="right")
        table.add_column("Avg Time", style="white", width=10, justify="right")
        table.add_column("Cost/Success", style="magenta", width=13, justify="right")
        table.add_column("Status", style="cyan", width=12)

        if not agents:
            table.add_row(
                "N/A", "No agents", "0", "Intern",
                "N/A", "N/A", "N/A", "Idle"
            )
            return table

        sorted_agents = sorted(
            agents.items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )

        for rank, (agent_name, agent_data) in enumerate(sorted_agents, start=1):
            xp = agent_data.get("xp", 0)
            level = agent_data.get("level", 1)
            success_rate = agent_data.get("success_rate", 0.0)
            avg_duration = agent_data.get("avg_duration_seconds", 0.0)
            cost_per_success = agent_data.get("cost_per_success_usd", 0.0)
            last_active = agent_data.get("last_active", "")

            status = self._determine_status(last_active)
            success_rate_str = f"{success_rate * 100:.1f}%"
            avg_time_str = self._format_duration(avg_duration)
            cost_str = f"${cost_per_success:.4f}" if cost_per_success > 0 else "N/A"
            level_title = LEVEL_TITLES.get(level, "Unknown")

            if rank == 1:
                agent_display = f"[gold1]{agent_name}[/gold1]"
                rank_display = f"[gold1]#{rank}[/gold1]"
            elif rank == 2:
                agent_display = f"[white]{agent_name}[/white]"
                rank_display = f"[white]#{rank}[/white]"
            elif rank == 3:
                agent_display = f"[#CD7F32]{agent_name}[/#CD7F32]"
                rank_display = f"[#CD7F32]#{rank}[/#CD7F32]"
            else:
                agent_display = agent_name
                rank_display = f"#{rank}"

            table.add_row(
                rank_display,
                agent_display,
                str(xp),
                f"[cyan]{level_title}[/cyan]",
                success_rate_str,
                avg_time_str,
                cost_str,
                status
            )

        return table

    def create_leaderboard_layout(self, state: dict) -> Layout:
        """Create complete leaderboard layout with header and table.

        Args:
            state: DashboardState dictionary

        Returns:
            Rich Layout with leaderboard components
        """
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="leaderboard")
        )

        layout["header"].update(self._create_project_header(state))
        layout["leaderboard"].update(
            Panel(
                self.create_leaderboard_table(state.get("agents", {})),
                border_style="cyan"
            )
        )

        return layout

    def create_initializing_layout(self) -> Layout:
        """Create layout for initializing state when metrics file doesn't exist.

        Returns:
            Rich Layout showing initializing state
        """
        layout = Layout()

        text = Text()
        text.append("\n\n", style="")
        text.append("Initializing Leaderboard...\n\n", style="bold yellow")
        text.append("Waiting for metrics file to be created.\n", style="dim")
        text.append("The leaderboard will update automatically when agents start working.\n", style="dim")

        panel = Panel(text, title="Agent Leaderboard", border_style="yellow")
        layout.update(panel)

        return layout

    @staticmethod
    def _create_project_header(state: dict) -> Panel:
        """Create project header with project name and update time."""
        project_name = state.get("project_name", "Unknown Project")
        updated_at = state.get("updated_at", "")
        total_agents = len(state.get("agents", {}))
        total_xp = sum(a.get("xp", 0) for a in state.get("agents", {}).values())

        if updated_at:
            try:
                updated_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                updated_str = updated_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except (ValueError, TypeError):
                updated_str = "Unknown"
        else:
            updated_str = "Never"

        text = Text()
        text.append(f"Project: ", style="bold")
        text.append(f"{project_name}\n", style="cyan bold")
        text.append(f"Total Agents: ", style="bold")
        text.append(f"{total_agents}  ", style="cyan")
        text.append(f"Total XP: ", style="bold")
        text.append(f"{total_xp}\n", style="yellow bold")
        text.append(f"Last Updated: ", style="bold")
        text.append(f"{updated_str}", style="dim")

        return Panel(text, title="Agent Leaderboard", border_style="green")

    @staticmethod
    def _determine_status(last_active: str) -> str:
        """Determine agent status based on last activity time."""
        if not last_active:
            return "[dim]Idle[/dim]"

        try:
            last_active_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            seconds_since = (now - last_active_dt).total_seconds()

            if seconds_since < 60:
                return "[green]Active[/green]"
            else:
                return "[dim]Idle[/dim]"
        except (ValueError, TypeError):
            return "[yellow]Unknown[/yellow]"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into human-readable duration string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
