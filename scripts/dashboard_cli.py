#!/usr/bin/env python3
"""Unified Dashboard CLI with multiple modes of operation.

Provides a comprehensive command-line interface for the Agent Status Dashboard
with support for multiple operational modes:

- DEFAULT (no flags): Show main dashboard with live updates
- --once: Run dashboard once without live updates
- --json: Output metrics as JSON instead of rich terminal UI
- --agent NAME: Show detailed view for a specific agent
- --leaderboard: Show leaderboard view sorted by XP
- --achievements: Show achievements view
- --serve: Start the web dashboard HTTP server

Usage:
    python scripts/dashboard_cli.py --project-dir generations/my-app
    python scripts/dashboard_cli.py --project-dir generations/my-app --once
    python scripts/dashboard_cli.py --project-dir generations/my-app --json
    python scripts/dashboard_cli.py --project-dir generations/my-app --agent coding
    python scripts/dashboard_cli.py --project-dir generations/my-app --leaderboard
    python scripts/dashboard_cli.py --project-dir generations/my-app --achievements
    python scripts/dashboard_cli.py --project-dir generations/my-app --serve
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

# Add repo root to path for package imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from dashboard.cli import (
    DashboardRenderer,
    MetricsFileMonitor,
    find_metrics_file,
    DEFAULT_REFRESH_RATE_MS,
    LeaderboardRenderer,
    AgentDetailRenderer,
    AchievementRenderer,
)


def find_project_metrics(project_dir: Optional[Path] = None) -> Path:
    """Find the metrics file for a project directory.

    Searches for .agent_metrics.json in the project directory first,
    then falls back to the standard find_metrics_file search.

    Args:
        project_dir: Optional project directory to search

    Returns:
        Path to metrics file (may not exist yet)
    """
    if project_dir:
        project_metrics = project_dir / ".agent_metrics.json"
        if project_metrics.exists():
            return project_metrics
        # Also check for metrics.json in a subdirectory
        subdir_metrics = project_dir / ".agent_metrics" / "metrics.json"
        if subdir_metrics.exists():
            return subdir_metrics
        # Default to .agent_metrics.json in the project dir
        return project_metrics

    return find_metrics_file()


def run_live_dashboard(
    console: Console,
    metrics_path: Path,
    refresh_rate_ms: int = DEFAULT_REFRESH_RATE_MS,
) -> None:
    """Run the live dashboard with continuous updates."""
    renderer = DashboardRenderer(console)
    monitor = MetricsFileMonitor(metrics_path)
    refresh_rate_sec = refresh_rate_ms / 1000.0

    with Live(
        renderer.create_initializing_layout(),
        console=console,
        refresh_per_second=1.0 / refresh_rate_sec,
        screen=True,
    ) as live:
        try:
            while True:
                state = monitor.load_metrics()
                if state is None:
                    live.update(renderer.create_initializing_layout())
                else:
                    live.update(renderer.create_dashboard_layout(state))
                time.sleep(refresh_rate_sec)
        except KeyboardInterrupt:
            console.print("\n[yellow]Dashboard stopped by user.[/yellow]")


def run_once_dashboard(console: Console, metrics_path: Path) -> None:
    """Run the dashboard once without live updates."""
    renderer = DashboardRenderer(console)
    monitor = MetricsFileMonitor(metrics_path)

    state = monitor.load_metrics()
    if state is None:
        console.print(renderer.create_initializing_layout())
    else:
        console.print(renderer.create_dashboard_layout(state))


def run_json_output(console: Console, metrics_path: Path) -> None:
    """Output metrics as JSON to stdout."""
    monitor = MetricsFileMonitor(metrics_path)
    state = monitor.load_metrics()

    if state is None:
        print(json.dumps({"error": "Metrics file not found or invalid"}, indent=2))
    else:
        print(json.dumps(state, indent=2))


def run_agent_detail(console: Console, metrics_path: Path, agent_name: str) -> None:
    """Show detailed view for a specific agent."""
    renderer = AgentDetailRenderer(console)
    monitor = MetricsFileMonitor(metrics_path)

    state = monitor.load_metrics()
    if state is None:
        console.print("[red]Error: Metrics file not found[/red]")
        return

    agents = state.get("agents", {})
    if agent_name not in agents:
        console.print(f"[red]Error: Agent '{agent_name}' not found[/red]")
        console.print(f"[dim]Available agents: {', '.join(agents.keys())}[/dim]")
        return

    agent_data = agents[agent_name]
    renderer.render_agent_detail(agent_name, agent_data, state)


def run_leaderboard(
    console: Console,
    metrics_path: Path,
    refresh_rate_ms: int = DEFAULT_REFRESH_RATE_MS,
    once: bool = False,
) -> None:
    """Show leaderboard view."""
    renderer = LeaderboardRenderer(console)
    monitor = MetricsFileMonitor(metrics_path)

    if once:
        state = monitor.load_metrics()
        if state is None:
            console.print(renderer.create_initializing_layout())
        else:
            console.print(renderer.create_leaderboard_layout(state))
    else:
        refresh_rate_sec = refresh_rate_ms / 1000.0
        with Live(
            renderer.create_initializing_layout(),
            console=console,
            refresh_per_second=1.0 / refresh_rate_sec,
            screen=True,
        ) as live:
            try:
                while True:
                    state = monitor.load_metrics()
                    if state is None:
                        live.update(renderer.create_initializing_layout())
                    else:
                        live.update(renderer.create_leaderboard_layout(state))
                    time.sleep(refresh_rate_sec)
            except KeyboardInterrupt:
                console.print("\n[yellow]Leaderboard stopped by user.[/yellow]")


def run_achievements(
    console: Console,
    metrics_path: Path,
    agent_name: Optional[str] = None,
    once: bool = False,
) -> None:
    """Show achievements view."""
    renderer = AchievementRenderer(console)
    monitor = MetricsFileMonitor(metrics_path)

    if once:
        state = monitor.load_metrics()
        if state is None:
            console.print("[red]Error: Metrics file not found[/red]")
        else:
            agents = state.get("agents", {})
            if agent_name:
                if agent_name not in agents:
                    console.print(f"[red]Error: Agent '{agent_name}' not found[/red]")
                    return
                console.print(renderer.create_achievements_grid(agent_name, agents[agent_name]))
            else:
                console.print(renderer.create_all_agents_achievements(agents))
    else:
        console.print("[dim]Achievements view (single update). Use --once for explicit mode.[/dim]")
        state = monitor.load_metrics()
        if state is None:
            console.print("[red]Error: Metrics file not found[/red]")
        else:
            agents = state.get("agents", {})
            if agent_name:
                if agent_name not in agents:
                    console.print(f"[red]Error: Agent '{agent_name}' not found[/red]")
                    return
                console.print(renderer.create_achievements_grid(agent_name, agents[agent_name]))
            else:
                console.print(renderer.create_all_agents_achievements(agents))


def run_web_server(metrics_path: Path, port: int, host: str) -> None:
    """Start the web dashboard HTTP server."""
    from dashboard.server import DashboardServer

    metrics_dir = metrics_path.parent
    server = DashboardServer(
        project_name="agent-engineers",
        metrics_dir=metrics_dir,
        port=port,
        host=host,
    )
    server.run()


def main():
    """Main entry point for the unified dashboard CLI."""
    parser = argparse.ArgumentParser(
        description="Agent Status Dashboard CLI - metrics visualization and web server",
        epilog="Examples:\n"
               "  %(prog)s --project-dir generations/my-app           # Live dashboard\n"
               "  %(prog)s --project-dir generations/my-app --once    # Single update\n"
               "  %(prog)s --project-dir generations/my-app --json    # JSON output\n"
               "  %(prog)s --project-dir generations/my-app --agent coding  # Agent detail\n"
               "  %(prog)s --project-dir generations/my-app --leaderboard   # Leaderboard\n"
               "  %(prog)s --project-dir generations/my-app --serve   # Web server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Mode arguments (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--json", action="store_true",
        help="Output metrics as JSON to stdout",
    )
    mode_group.add_argument(
        "--agent", type=str, metavar="NAME",
        help="Show detailed view for specific agent",
    )
    mode_group.add_argument(
        "--leaderboard", action="store_true",
        help="Show leaderboard view sorted by XP",
    )
    mode_group.add_argument(
        "--achievements", action="store_true",
        help="Show achievements view",
    )
    mode_group.add_argument(
        "--serve", action="store_true",
        help="Start the web dashboard HTTP server",
    )

    # Common arguments
    parser.add_argument(
        "--project-dir", type=Path, default=None,
        help="Project directory containing .agent_metrics.json",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run without live updates (applies to dashboard, leaderboard, achievements)",
    )
    parser.add_argument(
        "--refresh-rate", type=int, default=DEFAULT_REFRESH_RATE_MS,
        help=f"Refresh rate in milliseconds (default: {DEFAULT_REFRESH_RATE_MS}ms)",
    )
    parser.add_argument(
        "--port", type=int, default=8080,
        help="HTTP server port for --serve mode (default: 8080)",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="HTTP server host for --serve mode (default: 127.0.0.1)",
    )

    args = parser.parse_args()

    # Find metrics file
    metrics_path = find_project_metrics(args.project_dir)

    # Create console
    console = Console()

    # Print startup info for non-JSON, non-serve modes
    if not args.json and not args.serve:
        console.print("[cyan]Agent Status Dashboard CLI[/cyan]")
        console.print(f"[dim]Metrics file: {metrics_path}[/dim]")

    # Route to appropriate mode
    try:
        if args.serve:
            run_web_server(metrics_path, args.port, args.host)
        elif args.json:
            run_json_output(console, metrics_path)
        elif args.agent:
            run_agent_detail(console, metrics_path, args.agent)
        elif args.leaderboard:
            run_leaderboard(console, metrics_path, args.refresh_rate, once=args.once)
        elif args.achievements:
            run_achievements(console, metrics_path, once=args.once)
        else:
            # Default: live dashboard (or once if --once specified)
            if args.once:
                run_once_dashboard(console, metrics_path)
            else:
                console.print(f"[dim]Refresh rate: {args.refresh_rate}ms[/dim]")
                console.print("[dim]Press Ctrl+C to exit[/dim]\n")
                time.sleep(1)
                run_live_dashboard(console, metrics_path, args.refresh_rate)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", stderr=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
