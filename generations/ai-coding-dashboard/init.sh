#!/bin/bash

# AI Coding Dashboard - Development Environment Setup Script
# Sets up environment variables, copies .env, and starts dev servers

set -e  # Exit on any error

echo "=========================================="
echo "AI Coding Dashboard - Dev Environment Setup"
echo "=========================================="
echo ""

# Set NODE_ENV to development
export NODE_ENV=development
echo "[1/4] Setting NODE_ENV to development"

# Copy .env from parent directory
if [ -f "../../.env" ]; then
    echo "[2/4] Copying .env from parent directory..."
    cp ../../.env .env
    echo "      .env copied successfully"
    echo ""

    # Verify required variables
    if ! grep -q "OPENROUTER_API_KEY" .env 2>/dev/null; then
        echo "WARNING: OPENROUTER_API_KEY not found in .env"
    fi
    if ! grep -q "POSTGRES_URL" .env 2>/dev/null; then
        echo "WARNING: POSTGRES_URL not found in .env"
    fi
else
    echo "ERROR: .env file not found in parent directory (../../.env)"
    echo "Please ensure .env exists in the parent directory with:"
    echo "  - OPENROUTER_API_KEY"
    echo "  - POSTGRES_URL"
    exit 1
fi

# Check if dependencies are installed
echo "[3/4] Checking dependencies..."
if [ ! -d "node_modules" ]; then
    echo "      Installing npm dependencies..."
    npm install
else
    echo "      npm dependencies already installed"
fi

echo ""
echo "[4/4] Starting development servers..."
echo "=========================================="
echo ""
echo "Frontend: http://localhost:3010"
echo "Backend:  http://localhost:8000"
echo ""
echo "To start backend separately, run:"
echo "  cd agent && uvicorn main:app --reload --port 8000"
echo ""
echo "=========================================="
echo ""

# Start the Next.js dev server on port 3010
exec npm run dev -- -p 3010
