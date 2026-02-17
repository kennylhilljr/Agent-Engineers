#!/bin/bash
# Agent Dashboard - startup script
# Starts the aiohttp-based dashboard server.
#
# Usage:
#   ./init.sh                  Start on default port 8080
#   ./init.sh --port 9000      Start on custom port
#   ./init.sh --host 0.0.0.0   Bind to all network interfaces

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Install / verify dependencies
echo "Checking dependencies..."
pip install -q -r requirements.txt

echo "Starting Agent Status Dashboard server..."
echo "Dashboard will be available at: http://127.0.0.1:8080/"
echo ""

# Run the server; forward all CLI arguments (e.g. --port, --host)
python run_server.py "$@"
