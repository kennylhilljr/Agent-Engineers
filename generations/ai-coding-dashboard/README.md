# AI Coding Dashboard

## Overview

AI Coding Dashboard is a proof-of-concept generative UI application that demonstrates the power of Google's A2UI specification with CopilotKit's AG-UI protocol and Pydantic AI agents. Users upload an app specification (similar to app_spec.txt), and an autonomous coding agent executes the tasks while dynamically generating a custom dashboard using A2UI components. The agent emits declarative A2UI JSON describing UI components, AG-UI transports these specifications to the frontend, and CopilotKit renders them from a pre-approved component catalog - creating a unique, secure visualization tailored to each project.

## Target Audience

**Primary Users:** Developers building autonomous coding agents who want to visualize agent progress with dynamic, AI-generated dashboards.

**Key Pain Points:**
- Static dashboards don't adapt to different project types
- Hard to visualize what coding agents are doing in real-time
- No good way to approve high-risk changes mid-execution
- Progress tracking UIs require manual design for each project type

## Tech Stack

- **Frontend:** Next.js 14+ (App Router)
- **Styling:** Tailwind CSS + Shadcn/ui
- **UI Framework:** CopilotKit with A2UI renderer
- **UI Specification:** A2UI v0.8 (Google's declarative UI format)
- **Transport Protocol:** AG-UI (CopilotKit's agent-user interaction protocol)
- **Backend:** FastAPI (Python)
- **Agent Framework:** Pydantic AI with AG-UI integration
- **LLM:** Claude Sonnet 4.5 via OpenRouter
- **Database:** PostgreSQL (Neon)
- **Real-time:** Server-Sent Events (SSE) via AG-UI
- **Hosting:** Vercel (frontend) + Render/Railway (backend)

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- PostgreSQL database (or Neon serverless)
- OpenRouter API key

### Environment Setup

The `init.sh` script handles the setup process:

```bash
./init.sh
```

This will:
1. Set NODE_ENV to development
2. Copy .env from the parent directory (contains OPENROUTER_API_KEY and POSTGRES_URL)
3. Install dependencies
4. Start the Next.js dev server on port 3010

### Manual Setup

If you prefer to set up manually:

1. Install dependencies:
```bash
npm install
cd agent && pip install -r requirements.txt && cd ..
```

2. Copy environment variables:
```bash
cp ../../.env .env
```

3. Start the frontend (port 3010):
```bash
npm run dev
```

4. Start the backend in another terminal (port 8000):
```bash
cd agent && uvicorn main:app --reload --port 8000
```

## Configuration

### Frontend
- Dev server: `http://localhost:3010`
- Build: `npm run build`
- Production: `npm start`

### Backend
- Dev server: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- AG-UI endpoint: `http://localhost:8000/ag-ui/stream`

### Environment Variables

Required:
- `OPENROUTER_API_KEY` - Your OpenRouter API key for Claude Sonnet 4.5
- `POSTGRES_URL` - PostgreSQL connection string

Optional:
- `NODE_ENV` - Set to "development" or "production" (default: development)
- `BACKEND_PORT` - Port for FastAPI server (default: 8000)

## Project Structure

```
.
├── app/                    # Next.js frontend
│   ├── (dashboard)/        # Main dashboard routes
│   ├── api/                # API routes and proxies
│   └── layout.tsx          # Root layout with CopilotKit provider
├── components/             # React components
│   ├── a2ui-catalog/       # A2UI component implementations
│   └── ui/                 # Shadcn/ui base components
├── lib/                    # Utilities and configuration
│   ├── a2ui-catalog.ts     # A2UI catalog registration
│   └── copilot-provider.tsx # CopilotKit setup
├── agent/                  # Python backend
│   ├── main.py             # FastAPI app with AG-UI adapter
│   ├── agent.py            # Pydantic AI agent definition
│   ├── tools.py            # Agent tools for task execution
│   ├── models.py           # Pydantic data models
│   ├── a2ui_generator.py   # A2UI JSON component generation
│   └── requirements.txt     # Python dependencies
├── init.sh                 # Setup script
├── .env                    # Environment variables (git-ignored)
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## Features

### 1. Spec Upload & Parsing
Upload app_spec.txt files and the agent parses tasks, categories, and dependencies.

### 2. Dynamic Dashboard Generation
Agent analyzes project type and generates optimal A2UI layout:
- Kanban board for feature-based projects
- Timeline view for sequential projects
- Dependency graph for complex tasks

### 3. Real-time Task Execution Visualization
Watch tasks progress with live updates, file modifications, test results, and command logs.

### 4. A2UI Component Catalog
Pre-approved components for secure, deterministic UI rendering:
- TaskCard, ProgressRing, FileTree, TestResults
- ApprovalCard, ActivityItem, DecisionCard, ErrorCard
- MilestoneCard, DiffViewer

### 5. Human-in-the-Loop Workflows
Approve/reject high-risk actions, modify priorities, and interact via CopilotKit chat.

### 6. External Agent Integration
Claude Code and other external agents can push events to the dashboard API and receive human decisions.

## Development

### Running Tests

```bash
npm run test           # Frontend tests
cd agent && pytest     # Backend tests
```

### Building

```bash
npm run build
cd agent && python -m py_compile agent/
```

### Code Quality

```bash
npm run lint
```

## Deployment

### Frontend (Vercel)
```bash
vercel deploy
```

### Backend (Render/Railway)
See backend documentation for deployment instructions.

## Documentation

- [A2UI Specification](https://a2ui.io)
- [CopilotKit AG-UI Protocol](https://docs.copilotkit.ai)
- [Pydantic AI Documentation](https://docs.pydantic.dev/latest/concepts/ai/)
- [FastAPI Documentation](https://fastapi.tiangolo.com)

## Contributing

This is a sponsored YouTube demonstration project. For bug reports or feature requests, please open an issue on GitHub.

## License

MIT

## Credits

Built with [CopilotKit](https://copilotkit.ai), [Pydantic AI](https://docs.pydantic.dev/latest/concepts/ai/), and [Google A2UI](https://a2ui.io).
