# Agent-Engineers

A multi-agent engineering workflow system powered by Anthropic's Claude Agent SDK.

## Overview

Agent-Engineers is an AI-driven project management and development platform that integrates with Linear for issue tracking, enabling autonomous agents to plan, implement, and validate software requirements.

## Features

- AI agent workflow enforcement and orchestration
- Live reasoning stream display for real-time agent transparency
- Requirement sync to Linear (issue tracking integration)
- Edit requirements mid-flight for dynamic project adjustments
- Automated spec parsing and task decomposition

## Project Structure

- `app_spec.txt` - Application specification and requirements
- `.linear_project.json` - Linear project configuration and metadata
- `.claude_settings.json` - Claude agent settings
- `init.sh` - Project initialization script

## Getting Started

1. Clone the repository
2. Run `bash init.sh` to initialize the project environment
3. Configure your Linear API credentials in the environment
4. Launch the agent workflow

## Requirements

- Node.js (v18+) or Python (3.10+)
- Anthropic API key
- Linear API key (for issue tracking integration)

## License

MIT
