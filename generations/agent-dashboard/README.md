# Agent Dashboard

A web-based dashboard for multi-agent system monitoring and control.

## Overview

Agent Dashboard provides real-time visibility into multi-agent systems with intuitive controls for agent management, AI-powered chat interface with multi-provider support, and transparent reasoning capabilities.

## Features

- **AI Chat Interface**: Multi-provider AI support with streaming responses
- **Real-time Agent Monitoring**: Live status updates and performance metrics via WebSocket
- **Agent Controls**: Pause, resume, and edit agents on the fly
- **Reasoning Transparency**: View AI reasoning processes and decision paths
- **Multi-Provider Support**: Seamless integration with multiple AI providers

## Technology Stack

- **Backend**: Python (FastAPI/aiohttp) with WebSocket support
- **Frontend**: Single HTML file (no build step required)
- **Real-time Updates**: WebSocket for live agent status and chat
- **Deployment**: Containerized with development and production configurations

## Project Documentation

- **[agent_dashboard_requirements.md](./agent_dashboard_requirements.md)**: Comprehensive functional and technical requirements
- **[QA_updates.md](./QA_updates.md)**: QA and testing specifications
- **[LINEAR_SETUP_STATUS.md](./LINEAR_SETUP_STATUS.md)**: Issue tracking and project management details

## Setup Instructions

### Prerequisites

- Python 3.11+
- pip or uv package manager
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd agent-dashboard
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the development server:
```bash
./init.sh
```

The dashboard will be available at `http://localhost:8000`

## Development Workflow

### Project Structure

```
agent-dashboard/
├── scripts/
│   └── dashboard_server.py    # Main server entry point
├── frontend/                   # Frontend assets
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── init.sh                     # Development server startup
└── .gitignore                  # Git ignore rules
```

### Running Development Server

```bash
./init.sh
```

This will:
1. Activate the virtual environment (if it exists)
2. Install dependencies
3. Start the dashboard server

### Git Workflow

- Create feature branches from `main`
- Commit with descriptive messages
- Submit pull requests for review
- All commits include co-author attribution

## Contributing

When making changes, please:
1. Follow the existing code style
2. Include descriptive commit messages
3. Test your changes
4. Update documentation as needed

## License

See LICENSE file for details.
