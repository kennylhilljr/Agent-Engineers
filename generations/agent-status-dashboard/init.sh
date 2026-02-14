#\!/bin/bash
# Agent Status Dashboard - Development Server Startup

echo Starting Agent Status Dashboard
echo
pip install -r requirements.txt

echo Dependencies installed successfully

echo Starting CLI dashboard in live mode
python3 scripts/agent_dashboard.py --project-dir .
