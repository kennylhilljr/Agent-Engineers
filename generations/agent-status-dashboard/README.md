# Agent Status Dashboard

A real-time monitoring dashboard for multi-agent orchestrator systems, providing visibility into agent performance, operational costs, and team contributions.

## Overview

The Agent Status Dashboard is a comprehensive monitoring solution designed for teams running sophisticated multi-agent systems. It provides real-time visibility into agent activity, performance metrics, cost tracking, and contribution analytics in a beautiful CLI-based interface.

## Key Features

### 1. Real-time Visibility
- Live agent status monitoring
- Task execution tracking
- Event streaming and log viewing
- Performance metrics aggregation

### 2. Cost Tracking
- Token usage analytics
- API call costs per agent
- Total operational expense reporting
- Cost trends and optimization recommendations

### 3. Contribution Metrics
- Team member contribution tracking
- Productivity analytics
- Performance leaderboards
- Individual impact assessment

### 4. Gamification
- Achievement badges
- Streak tracking
- Milestone rewards
- Competitive scoreboards

## Architecture



## Getting Started

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Installation

1. Clone the repository:
git clone repository-url
cd agent-status-dashboard

2. Install dependencies:
pip install -r requirements.txt

3. Run the development server:
./init.sh

## Usage Examples

Start the live dashboard:
python scripts/agent_dashboard.py --project-dir . --mode live

View metrics summary:
python scripts/agent_dashboard.py --project-dir . --report summary

Export data:
python scripts/agent_dashboard.py --project-dir . --export json

## Contributing

1. Create a feature branch
2. Make your changes
3. Write tests
4. Submit a pull request

## License

MIT License
