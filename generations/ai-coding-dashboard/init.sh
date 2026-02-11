#!/bin/bash

# AI Coding Dashboard - Development Environment Initialization Script
# This script sets up both frontend and backend for local development

set -e

echo "=========================================="
echo "AI Coding Dashboard - Dev Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Check Node.js
echo -e "${BLUE}Checking Node.js installation...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}Node.js not found. Please install Node.js 18+${NC}"
    exit 1
fi
NODE_VERSION=$(node -v)
echo -e "${GREEN}Node.js ${NODE_VERSION} found${NC}"
echo ""

# Check Python
echo -e "${BLUE}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python 3 not found. Please install Python 3.11+${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}${PYTHON_VERSION} found${NC}"
echo ""

# Frontend Setup
echo -e "${BLUE}Setting up Frontend...${NC}"
if [ -d "frontend" ]; then
    cd frontend

    if [ ! -d "node_modules" ]; then
        echo "Installing Node dependencies..."
        npm install
    else
        echo "Node modules already installed, updating..."
        npm update
    fi

    echo -e "${GREEN}Frontend setup complete${NC}"
    cd "$PROJECT_ROOT"
else
    echo -e "${YELLOW}Frontend directory not found. Skipping frontend setup.${NC}"
fi
echo ""

# Backend Setup
echo -e "${BLUE}Setting up Backend...${NC}"
if [ -d "backend" ]; then
    cd backend

    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        echo "Creating Python virtual environment..."
        python3 -m venv venv
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Install dependencies
    if [ -f "requirements.txt" ]; then
        echo "Installing Python dependencies..."
        pip install --upgrade pip
        pip install -r requirements.txt
    else
        echo -e "${YELLOW}requirements.txt not found. Skipping pip install.${NC}"
    fi

    # Deactivate virtual environment
    deactivate

    echo -e "${GREEN}Backend setup complete${NC}"
    cd "$PROJECT_ROOT"
else
    echo -e "${YELLOW}Backend directory not found. Skipping backend setup.${NC}"
fi
echo ""

# Environment Configuration
echo -e "${BLUE}Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cat > .env << 'EOF'
# Jira Configuration
JIRA_API_TOKEN=your-token-here
JIRA_BASE_URL=https://your-instance.atlassian.net

# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your-signing-secret

# AI Configuration
AI_API_KEY=your-api-key

# Database Configuration (optional)
DATABASE_URL=postgresql://user:password@localhost:5432/ai_dashboard

# Redis Configuration (optional)
REDIS_URL=redis://localhost:6379/0

# Application Settings
DEBUG=true
ENVIRONMENT=development
FRONTEND_PORT=3010
BACKEND_PORT=8000
EOF
    echo -e "${YELLOW}Created .env file. Please update with your credentials.${NC}"
else
    echo -e "${GREEN}.env file already exists${NC}"
fi
echo ""

echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Update .env with your credentials:"
echo "   - Jira API token"
echo "   - Slack bot token"
echo "   - AI API key"
echo ""
echo "2. Start development servers:"
echo "   Frontend: npm run dev (in frontend/ directory)"
echo "   Backend:  python main.py (in backend/ directory)"
echo ""
echo "   Or use this command from project root:"
echo "   ./init.sh start"
echo ""
echo "3. Frontend will be available at: http://localhost:3010"
echo "   Backend will be available at: http://localhost:8000"
echo "   API docs at: http://localhost:8000/docs"
echo ""

# Optional: Start servers if 'start' argument provided
if [ "$1" == "start" ]; then
    echo -e "${BLUE}Starting development servers...${NC}"
    echo ""

    # Start backend in background
    if [ -d "backend" ]; then
        echo "Starting backend on port 8000..."
        cd backend
        source venv/bin/activate
        python main.py > backend.log 2>&1 &
        BACKEND_PID=$!
        cd "$PROJECT_ROOT"
        echo -e "${GREEN}Backend started (PID: $BACKEND_PID)${NC}"
    fi
    echo ""

    # Start frontend
    if [ -d "frontend" ]; then
        echo "Starting frontend on port 3010..."
        cd frontend
        npm run dev
    fi
fi
