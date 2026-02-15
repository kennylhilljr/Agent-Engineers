#!/bin/bash
# Start the Agent Dashboard development server

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install dependencies
pip install -r requirements.txt

# Start the dashboard server
python scripts/dashboard_server.py --project-dir .
