#!/usr/bin/env python3
"""Dashboard Server - Phase 1: Foundation

Provides an async HTTP server that serves the agent status dashboard with real-time metrics.

Usage:
    python scripts/dashboard_server.py --project-dir /path/to/project

Features:
- Async HTTP server on port 8420 using aiohttp
- Single-file HTML dashboard with agent status panel
- REST API endpoints: /api/health, /api/metrics, /api/agents
- Real-time data from .agent_metrics.json via MetricsStore
- Auto-opens browser on startup

Requirements:
- aiohttp, aiohttp-cors
- MetricsStore from dashboard.metrics_store
- AgentProfile, DashboardState from dashboard.metrics
"""

import argparse
import asyncio
import logging
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiohttp
import aiohttp_cors
from aiohttp import web

# Add project root to path so we can import dashboard modules
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.metrics import AgentProfile, DashboardState
from dashboard.metrics_store import MetricsStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Server configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8420
DEFAULT_PROJECT_NAME = "agent-dashboard"


class DashboardServer:
    """Async HTTP server for the Agent Status Dashboard.

    Serves a single-page HTML dashboard showing real-time agent metrics
    loaded from .agent_metrics.json via MetricsStore.
    """

    def __init__(
        self,
        project_dir: Path,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        project_name: str = DEFAULT_PROJECT_NAME
    ):
        """Initialize dashboard server.

        Args:
            project_dir: Path to project directory containing .agent_metrics.json
            host: Host IP to bind to (default: 127.0.0.1)
            port: Port to listen on (default: 8420)
            project_name: Name of the project for display
        """
        self.project_dir = Path(project_dir).resolve()
        self.host = host
        self.port = port
        self.project_name = project_name

        # Initialize MetricsStore
        self.metrics_store = MetricsStore(
            project_name=project_name,
            metrics_dir=self.project_dir
        )

        # Web app and routes
        self.app = web.Application()
        self._setup_routes()
        self._setup_cors()

        logger.info(f"Dashboard server initialized for project: {project_name}")
        logger.info(f"Metrics directory: {self.project_dir}")

    def _setup_routes(self) -> None:
        """Set up HTTP routes for the dashboard and REST API."""
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/health', self.handle_health)
        self.app.router.add_get('/api/metrics', self.handle_metrics)
        self.app.router.add_get('/api/agents', self.handle_agents)

    def _setup_cors(self) -> None:
        """Set up CORS to allow browser access from any origin."""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })

        # Apply CORS to all routes
        for route in list(self.app.router.routes()):
            try:
                cors.add(route)
            except ValueError:
                # Route already has CORS, skip
                pass

    async def handle_index(self, request: web.Request) -> web.Response:
        """Serve the main dashboard HTML page.

        Returns a single-file HTML page with embedded CSS and JavaScript
        that displays all agent metrics in a responsive dashboard layout.
        """
        html = self._generate_dashboard_html()
        return web.Response(
            text=html,
            content_type='text/html',
            charset='utf-8'
        )

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint.

        Returns:
            JSON with server status, uptime, and metrics file info
        """
        metrics_path = self.project_dir / ".agent_metrics.json"

        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "server": {
                "host": self.host,
                "port": self.port,
                "project_name": self.project_name,
                "project_dir": str(self.project_dir)
            },
            "metrics_file": {
                "path": str(metrics_path),
                "exists": metrics_path.exists(),
                "size_bytes": metrics_path.stat().st_size if metrics_path.exists() else 0
            }
        }

        return web.json_response(health_data)

    async def handle_metrics(self, request: web.Request) -> web.Response:
        """Get full dashboard metrics.

        Returns:
            JSON with complete DashboardState including all agents, events, and sessions
        """
        try:
            state = self.metrics_store.load()
            return web.json_response(state)
        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
            return web.json_response(
                {"error": f"Failed to load metrics: {str(e)}"},
                status=500
            )

    async def handle_agents(self, request: web.Request) -> web.Response:
        """Get agent profiles only.

        Returns:
            JSON array of all agent profiles sorted by level (descending)
        """
        try:
            state = self.metrics_store.load()
            agents = list(state["agents"].values())

            # Sort by level (descending), then by XP (descending)
            agents.sort(key=lambda a: (-a["level"], -a["xp"]))

            return web.json_response({"agents": agents})
        except Exception as e:
            logger.error(f"Error loading agents: {e}")
            return web.json_response(
                {"error": f"Failed to load agents: {str(e)}"},
                status=500
            )

    def _generate_dashboard_html(self) -> str:
        """Generate the complete single-file HTML dashboard.

        Returns:
            HTML string with embedded CSS and JavaScript
        """
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Status Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        h1 {
            font-size: 32px;
            color: #667eea;
            margin-bottom: 10px;
        }

        .subtitle {
            color: #666;
            font-size: 16px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .stat-label {
            font-size: 12px;
            text-transform: uppercase;
            color: #999;
            margin-bottom: 8px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }

        .stat-value {
            font-size: 28px;
            font-weight: bold;
            color: #333;
        }

        .agents-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }

        .agent-card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .agent-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 12px rgba(0, 0, 0, 0.15);
        }

        .agent-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 2px solid #f0f0f0;
        }

        .agent-name {
            font-size: 20px;
            font-weight: bold;
            color: #667eea;
            text-transform: capitalize;
        }

        .agent-level {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
        }

        .agent-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 16px;
        }

        .stat-item {
            display: flex;
            flex-direction: column;
        }

        .stat-item-label {
            font-size: 11px;
            color: #999;
            text-transform: uppercase;
            margin-bottom: 4px;
        }

        .stat-item-value {
            font-size: 16px;
            font-weight: 600;
            color: #333;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin: 8px 0;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 4px;
            transition: width 0.3s ease;
        }

        .tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }

        .tag {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }

        .tag-strength {
            background: #d4edda;
            color: #155724;
        }

        .tag-achievement {
            background: #fff3cd;
            color: #856404;
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .status-active {
            background: #28a745;
            box-shadow: 0 0 8px rgba(40, 167, 69, 0.5);
        }

        .status-idle {
            background: #ffc107;
        }

        .status-inactive {
            background: #dc3545;
        }

        .error-message {
            background: #f8d7da;
            color: #721c24;
            padding: 12px;
            border-radius: 8px;
            margin-top: 12px;
            font-size: 12px;
            border-left: 4px solid #dc3545;
        }

        .last-active {
            font-size: 12px;
            color: #666;
            margin-top: 8px;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 18px;
        }

        .refresh-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }

        .refresh-btn:hover {
            transform: scale(1.05);
        }

        .refresh-btn:active {
            transform: scale(0.95);
        }

        @media (max-width: 768px) {
            .agents-grid {
                grid-template-columns: 1fr;
            }

            .stats-grid {
                grid-template-columns: 1fr 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Agent Status Dashboard</h1>
            <p class="subtitle">Real-time monitoring of all 13 agents</p>
            <button class="refresh-btn" onclick="loadDashboard()">Refresh</button>
        </header>

        <div id="stats" class="stats-grid">
            <!-- Global stats will be loaded here -->
        </div>

        <div id="agents" class="agents-grid">
            <div class="loading">Loading agent data...</div>
        </div>
    </div>

    <script>
        // Global state
        let dashboardData = null;

        // Load dashboard data from API
        async function loadDashboard() {
            try {
                const response = await fetch('/api/metrics');
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                dashboardData = await response.json();
                renderDashboard();
            } catch (error) {
                console.error('Error loading dashboard:', error);
                document.getElementById('agents').innerHTML =
                    `<div class="error-message">Failed to load dashboard data: ${error.message}</div>`;
            }
        }

        // Render the complete dashboard
        function renderDashboard() {
            if (!dashboardData) return;

            renderStats();
            renderAgents();
        }

        // Render global statistics
        function renderStats() {
            const stats = [
                { label: 'Total Sessions', value: dashboardData.total_sessions },
                { label: 'Total Tokens', value: formatNumber(dashboardData.total_tokens) },
                { label: 'Total Cost', value: `$${dashboardData.total_cost_usd.toFixed(2)}` },
                { label: 'Active Agents', value: Object.keys(dashboardData.agents).length }
            ];

            document.getElementById('stats').innerHTML = stats.map(stat => `
                <div class="stat-card">
                    <div class="stat-label">${stat.label}</div>
                    <div class="stat-value">${stat.value}</div>
                </div>
            `).join('');
        }

        // Render all agent cards
        function renderAgents() {
            const agents = Object.values(dashboardData.agents);

            // Sort by level (desc), then XP (desc)
            agents.sort((a, b) => {
                if (b.level !== a.level) return b.level - a.level;
                return b.xp - a.xp;
            });

            document.getElementById('agents').innerHTML = agents.map(agent =>
                renderAgentCard(agent)
            ).join('');
        }

        // Render a single agent card
        function renderAgentCard(agent) {
            const status = getAgentStatus(agent);
            const successRate = (agent.success_rate * 100).toFixed(1);

            return `
                <div class="agent-card">
                    <div class="agent-header">
                        <div class="agent-name">
                            <span class="status-indicator status-${status}"></span>
                            ${agent.agent_name.replace(/_/g, ' ')}
                        </div>
                        <div class="agent-level">Level ${agent.level}</div>
                    </div>

                    <div class="agent-stats">
                        <div class="stat-item">
                            <div class="stat-item-label">Invocations</div>
                            <div class="stat-item-value">${agent.total_invocations}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-item-label">Success Rate</div>
                            <div class="stat-item-value">${successRate}%</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-item-label">XP</div>
                            <div class="stat-item-value">${formatNumber(agent.xp)}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-item-label">Streak</div>
                            <div class="stat-item-value">${agent.current_streak} / ${agent.best_streak}</div>
                        </div>
                    </div>

                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${successRate}%"></div>
                    </div>

                    ${renderAgentContributions(agent)}

                    ${renderAgentTags(agent)}

                    ${agent.last_error ? `
                        <div class="error-message">
                            <strong>Last Error:</strong> ${agent.last_error}
                        </div>
                    ` : ''}

                    ${agent.last_active ? `
                        <div class="last-active">
                            Last active: ${formatTimestamp(agent.last_active)}
                        </div>
                    ` : ''}
                </div>
            `;
        }

        // Render agent-specific contributions
        function renderAgentContributions(agent) {
            const contributions = [];

            if (agent.commits_made > 0) contributions.push(`${agent.commits_made} commits`);
            if (agent.prs_created > 0) contributions.push(`${agent.prs_created} PRs`);
            if (agent.files_created > 0) contributions.push(`${agent.files_created} files created`);
            if (agent.tests_written > 0) contributions.push(`${agent.tests_written} tests`);
            if (agent.issues_created > 0) contributions.push(`${agent.issues_created} issues created`);
            if (agent.issues_completed > 0) contributions.push(`${agent.issues_completed} issues completed`);
            if (agent.messages_sent > 0) contributions.push(`${agent.messages_sent} messages`);
            if (agent.reviews_completed > 0) contributions.push(`${agent.reviews_completed} reviews`);

            if (contributions.length === 0) return '';

            return `
                <div class="stat-item" style="grid-column: 1 / -1; margin-top: 8px;">
                    <div class="stat-item-label">Contributions</div>
                    <div class="stat-item-value" style="font-size: 13px;">${contributions.join(', ')}</div>
                </div>
            `;
        }

        // Render strengths and achievements tags
        function renderAgentTags(agent) {
            const tags = [];

            // Add strengths
            agent.strengths.forEach(strength => {
                tags.push(`<span class="tag tag-strength">${strength.replace(/_/g, ' ')}</span>`);
            });

            // Add top achievements (max 3)
            agent.achievements.slice(0, 3).forEach(achievement => {
                tags.push(`<span class="tag tag-achievement">${achievement.replace(/_/g, ' ')}</span>`);
            });

            if (tags.length === 0) return '';

            return `<div class="tags">${tags.join('')}</div>`;
        }

        // Determine agent status based on activity
        function getAgentStatus(agent) {
            if (!agent.last_active) return 'inactive';

            const lastActive = new Date(agent.last_active);
            const now = new Date();
            const hoursSinceActive = (now - lastActive) / (1000 * 60 * 60);

            if (hoursSinceActive < 1) return 'active';
            if (hoursSinceActive < 24) return 'idle';
            return 'inactive';
        }

        // Format large numbers with commas
        function formatNumber(num) {
            return num.toLocaleString();
        }

        // Format ISO timestamp to relative time
        function formatTimestamp(iso) {
            if (!iso) return 'Never';

            const date = new Date(iso);
            const now = new Date();
            const diff = now - date;

            const minutes = Math.floor(diff / 60000);
            const hours = Math.floor(diff / 3600000);
            const days = Math.floor(diff / 86400000);

            if (minutes < 1) return 'Just now';
            if (minutes < 60) return `${minutes}m ago`;
            if (hours < 24) return `${hours}h ago`;
            if (days < 7) return `${days}d ago`;

            return date.toLocaleDateString();
        }

        // Auto-refresh every 5 seconds
        setInterval(loadDashboard, 5000);

        // Initial load
        loadDashboard();
    </script>
</body>
</html>
"""

    async def start(self, open_browser: bool = True) -> None:
        """Start the dashboard server.

        Args:
            open_browser: Whether to automatically open browser on startup
        """
        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        url = f"http://{self.host}:{self.port}"
        logger.info(f"Dashboard server running at {url}")

        # Open browser
        if open_browser:
            logger.info(f"Opening browser to {url}")
            webbrowser.open(url)

        # Keep server running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutting down dashboard server...")
        finally:
            await runner.cleanup()


async def main():
    """Main entry point for the dashboard server."""
    parser = argparse.ArgumentParser(
        description="Agent Status Dashboard Server - Phase 1: Foundation"
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Path to project directory containing .agent_metrics.json (default: current directory)"
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Host IP to bind to (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--project-name",
        default=DEFAULT_PROJECT_NAME,
        help=f"Project name for display (default: {DEFAULT_PROJECT_NAME})"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't automatically open browser on startup"
    )

    args = parser.parse_args()

    # Validate project directory
    if not args.project_dir.exists():
        logger.error(f"Project directory does not exist: {args.project_dir}")
        sys.exit(1)

    # Create and start server
    server = DashboardServer(
        project_dir=args.project_dir,
        host=args.host,
        port=args.port,
        project_name=args.project_name
    )

    await server.start(open_browser=not args.no_browser)


if __name__ == "__main__":
    asyncio.run(main())
