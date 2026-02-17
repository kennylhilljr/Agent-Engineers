#!/bin/bash
# init.sh - Agent-Engineers Code Improvements Project
# Initializes the development environment

set -e

echo "=== Agent-Engineers Code Improvements ==="
echo "Initializing development environment..."

# Check Python version
python_version=$(python3 --version 2>&1)
echo "Python: $python_version"

# Check if we're in the right directory
if [ ! -f "app_spec.txt" ]; then
    echo "ERROR: Please run this script from the project root directory"
    exit 1
fi

# Navigate to the actual codebase (parent of generations)
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "Project root: $PROJECT_ROOT"

# Install dependencies if requirements.txt exists
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo "Installing dependencies..."
    pip install -r "$PROJECT_ROOT/requirements.txt"
fi

# Run tests if available
if [ -d "$PROJECT_ROOT/tests" ]; then
    echo "Running tests..."
    cd "$PROJECT_ROOT"
    python -m pytest tests/ -v --tb=short 2>/dev/null || echo "Some tests may be missing (expected for new project)"
    cd -
fi

echo ""
echo "=== Setup Complete ==="
echo "Linear Project: Agent-Engineers Code Improvements"
echo "Issues: AI-201 through AI-211"
echo ""
echo "Next steps:"
echo "  1. Review .linear_project.json for current issue status"
echo "  2. Start working on AI-201: Expand Test Coverage"
echo "  3. Run: python -m pytest tests/ -v --cov=. --cov-report=html"
