# AI Coding Dashboard

A full-stack application integrating AI-powered development workflows with project management tools (Jira) and real-time collaboration features.

## Tech Stack

### Frontend
- React 18+ with TypeScript
- Vite for build tooling
- A2UI component library
- TailwindCSS for styling
- Socket.io for real-time updates

### Backend
- Python 3.11+
- FastAPI for REST API
- WebSocket support for real-time features
- Jira API integration
- Slack bot integration

### Infrastructure
- Docker containerization
- Docker Compose for local development
- GitHub Actions for CI/CD

## Features

- AI-powered code generation and analysis
- Jira ticket management and synchronization
- Slack integration for notifications
- Real-time collaboration dashboard
- Agent-based task automation
- Code review assistance

## Project Structure

```
ai-coding-dashboard/
├── frontend/              # React TypeScript application
│   ├── src/
│   ├── public/
│   └── vite.config.ts
├── backend/              # Python FastAPI server
│   ├── app/
│   ├── config/
│   └── main.py
├── agents/               # AI agents for automation
├── docker-compose.yml    # Local dev environment
├── README.md
└── init.sh              # Development setup script
```

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- Docker & Docker Compose (optional, for containerized setup)

### Installation

Run the initialization script to set up both frontend and backend:

```bash
chmod +x init.sh
./init.sh
```

This will:
1. Install frontend dependencies (runs `npm install` in frontend/)
2. Set up Python virtual environment and install backend dependencies
3. Configure environment variables from templates

### Development Servers

Once initialized, the dev servers run on:

- **Frontend**: http://localhost:3010
- **Backend**: http://localhost:8000

For API documentation, visit: http://localhost:8000/docs

### Environment Configuration

Create a `.env` file in the project root:

```env
JIRA_API_TOKEN=your-token
JIRA_BASE_URL=your-jira-instance
SLACK_BOT_TOKEN=your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
AI_API_KEY=your-ai-api-key
```

## A2UI Components

The frontend uses A2UI component library for consistent UI patterns:

- Button, Input, Select components
- Form validation helpers
- Modal and Dialog components
- Table and List components
- Notification system
- Theme provider

See `/frontend/src/components` for implemented components.

## Jira Integration

The dashboard tracks development tasks in Jira with:

- Automatic ticket creation from AI suggestions
- Status synchronization
- Sprint planning support
- Link to Linear issues via custom fields

## Running Tests

### Frontend Tests
```bash
cd frontend && npm test
```

### Backend Tests
```bash
cd backend && pytest
```

## Docker Setup

For containerized local development:

```bash
docker-compose up -d
```

This starts:
- Frontend dev server on port 3010
- Backend API on port 8000
- PostgreSQL database (if configured)
- Redis cache (if configured)

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and commit with descriptive messages
3. Push and create a pull request
4. Reference Jira issues in commit messages and PR descriptions

## Support

For issues or questions, please create a GitHub issue or contact the development team.

## License

MIT
