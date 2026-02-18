# Agent Dashboard Developer Guide

This guide provides comprehensive instructions for developers working with the Agent Dashboard system.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Architecture Overview](#architecture-overview)
3. [Core Modules](#core-modules)
4. [Working with Agents](#working-with-agents)
5. [AI Provider Bridges](#ai-provider-bridges)
6. [Common Development Tasks](#common-development-tasks)
7. [Testing Guide](#testing-guide)
8. [Security Considerations](#security-considerations)

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Node.js 18+ (for MCP servers and Playwright)
- Git
- Virtual environment tool (venv or uv)

### Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd agent-dashboard

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys and configuration
```

### Environment Configuration

Key environment variables:

```bash
# Arcade MCP Gateway (Required)
ARCADE_API_KEY=your_arcade_api_key
ARCADE_GATEWAY_SLUG=your_gateway_slug
ARCADE_USER_ID=your_email@example.com

# Model Selection (Optional)
ORCHESTRATOR_MODEL=haiku  # haiku, sonnet, or opus
CODING_AGENT_MODEL=sonnet
LINEAR_AGENT_MODEL=haiku
GITHUB_AGENT_MODEL=haiku
SLACK_AGENT_MODEL=haiku

# GitHub Integration (Optional)
GITHUB_REPO=owner/repo-name

# Slack Integration (Optional)
SLACK_CHANNEL=channel-name
SLACK_BOT_TOKEN=xoxb-your-token

# AI Provider Bridges (Optional)
CHATGPT_AUTH_TYPE=codex-oauth  # or session-token
OPENAI_API_KEY=your_openai_key
GEMINI_AUTH_TYPE=cli-oauth  # or api-key or vertex-ai
GROQ_API_KEY=your_groq_key
KIMI_API_KEY=your_kimi_key
```

## Architecture Overview

### System Architecture

The Agent Dashboard uses a multi-agent orchestration pattern:

```
Orchestrator (Haiku/Sonnet/Opus)
├── Linear Agent (Issue tracking)
├── Coding Agent (Implementation)
├── GitHub Agent (Version control)
├── PR Reviewer Agent (Code review)
├── Slack Agent (Notifications)
└── AI Provider Agents
    ├── ChatGPT Agent
    ├── Gemini Agent
    ├── Groq Agent
    ├── KIMI Agent
    └── Windsurf Agent
```

### Key Concepts

1. **Orchestrator**: Central coordinator that delegates tasks to specialized agents
2. **Sub-Agents**: Specialized agents with focused responsibilities
3. **MCP Servers**: Model Context Protocol servers for external integrations
4. **Bridges**: Adapters for external AI providers
5. **Security Hooks**: Pre-tool-use validation for bash commands

## Core Modules

### client.py - Claude SDK Client Configuration

The `client` module configures the Claude Agent SDK client with security settings and MCP servers.

#### Example: Creating a Client

```python
from pathlib import Path
from client import create_client

# Create a client for a project
project_dir = Path("./my-project")
client = create_client(
    project_dir=project_dir,
    model="claude-sonnet-4-5-20250929",
    cwd=None,  # Optional: override working directory
    agent_overrides=None  # Optional: custom agent definitions
)

# Use the client in an async context
async with client:
    await client.query("Implement feature X")
    async for msg in client.receive_response():
        # Process messages
        pass
```

#### Security Configuration

The client automatically configures three security layers:

1. **Sandbox**: OS-level bash command isolation
2. **Permissions**: File operations restricted to project directory
3. **Security Hooks**: Bash command allowlist validation

```python
from client import create_security_settings, write_security_settings

# Create security settings
settings = create_security_settings()

# Write to project directory
settings_file = write_security_settings(project_dir, settings)
```

### agent.py - Agent Session Logic

The `agent` module provides core functions for running autonomous coding sessions.

#### Example: Running an Agent Session

```python
import asyncio
from pathlib import Path
from client import create_client
from agent import run_agent_session

async def main():
    project_dir = Path("./my-project")
    client = create_client(project_dir, "claude-sonnet-4-5-20250929")

    async with client:
        result = await run_agent_session(
            client=client,
            message="Implement the login feature",
            project_dir=project_dir
        )

        if result.status == "complete":
            print("Project complete!")
        elif result.status == "error":
            print(f"Error: {result.response}")
        else:
            print("Session completed, ready to continue")

asyncio.run(main())
```

#### Running the Autonomous Loop

```python
from agent import run_autonomous_agent

async def main():
    await run_autonomous_agent(
        project_dir=Path("./my-project"),
        model="claude-sonnet-4-5-20250929",
        max_iterations=5  # Optional: limit iterations
    )

asyncio.run(main())
```

### security.py - Bash Command Validation

The `security` module implements allowlist-based command validation.

#### Example: Custom Command Validation

```python
from security import validate_bash_command, ALLOWED_COMMANDS

# Add custom commands to allowlist
ALLOWED_COMMANDS.add("my-custom-tool")

# Validate a command
result = validate_bash_command("ls -la")
if result.allowed:
    print("Command allowed")
else:
    print(f"Command blocked: {result.reason}")
```

#### Understanding the Security Hook

```python
from claude_agent_sdk import PreToolUseHookInput
from security import bash_security_hook

# The security hook is called before bash commands execute
hook_input = PreToolUseHookInput(
    tool_use_id="tool_123",
    tool_name="Bash",
    tool_input={"command": "rm -rf /"}
)

response = bash_security_hook(hook_input, None)
# Response will block dangerous commands
```

### prompts.py - Prompt Template Management

The `prompts` module handles loading and managing prompt templates.

#### Example: Working with Prompts

```python
from pathlib import Path
from prompts import (
    load_prompt,
    get_initializer_task,
    get_continuation_task,
    copy_spec_to_project
)

# Load a custom prompt
custom_prompt = load_prompt("my_custom_prompt")

# Get initialization task
init_task = get_initializer_task(Path("./my-project"))

# Get continuation task
cont_task = get_continuation_task(Path("./my-project"))

# Copy spec file to project
copy_spec_to_project(Path("./my-project"))
```

## Working with Agents

### Agent Definitions

Agents are defined in `agents/definitions.py`:

```python
from agents.definitions import AGENT_DEFINITIONS

# Access specific agent
linear_agent = AGENT_DEFINITIONS["linear"]
print(f"Linear agent model: {linear_agent['model']}")
print(f"Linear agent prompt: {linear_agent['system_prompt']}")
```

### Creating Custom Agents

```python
from agents.definitions import create_agent_definition

# Define a custom agent
custom_agent = create_agent_definition(
    name="custom",
    model="claude-sonnet-4-5-20250929",
    prompt_file="custom_agent_prompt"
)

# Use in client
agent_overrides = {
    **AGENT_DEFINITIONS,
    "custom": custom_agent
}

client = create_client(
    project_dir=project_dir,
    model="haiku",
    agent_overrides=agent_overrides
)
```

### Delegating to Sub-Agents

Within an orchestrator prompt or agent implementation:

```markdown
Use the Task tool to delegate to specialized agents:

- `Task(agent="linear", task="Create issue for feature X")`
- `Task(agent="coding", task="Implement feature X")`
- `Task(agent="github", task="Create PR for feature X")`
- `Task(agent="slack", task="Notify team about feature X")`
```

## AI Provider Bridges

### ChatGPT Bridge

The ChatGPT bridge provides access to OpenAI models.

#### Example: Using ChatGPT Bridge

```python
from bridges.openai_bridge import OpenAIBridge

# Create bridge from environment
bridge = OpenAIBridge.from_env()

# Create session
session = bridge.create_session(
    model="gpt-4o",
    system_prompt="You are a helpful coding assistant"
)

# Send message
response = bridge.send_message(session, "Explain async/await in Python")
print(response.content)

# Check authentication status
auth_info = bridge.get_auth_info()
print(auth_info)
```

#### Async Usage

```python
import asyncio

async def main():
    bridge = OpenAIBridge.from_env()
    session = bridge.create_session(model="gpt-4o")

    # Async send
    response = await bridge.send_message_async(session, "Hello!")
    print(response.content)

    # Streaming
    async for token in bridge.stream_response(session, "Count to 10"):
        print(token, end="", flush=True)

asyncio.run(main())
```

### Gemini Bridge

```python
from bridges.gemini_bridge import GeminiBridge

# Create bridge
bridge = GeminiBridge.from_env()

# Create session
session = bridge.create_session(model="gemini-2.5-flash")

# Send message
response = bridge.send_message(session, "Analyze this code...")
print(response.content)
```

### Groq Bridge

```python
from bridges.groq_bridge import GroqBridge

# Create bridge
bridge = GroqBridge.from_env()

# Create session
session = bridge.create_session(model="llama-3.3-70b-versatile")

# Ultra-fast inference
response = bridge.send_message(session, "Quick task...")
```

## Common Development Tasks

### Task 1: Add a New Agent

1. Create prompt file in `prompts/`:

```bash
touch prompts/my_agent_prompt.md
```

2. Add agent definition in `agents/definitions.py`:

```python
"my_agent": {
    "model": get_agent_model("MY_AGENT_MODEL", "haiku"),
    "system_prompt": load_agent_prompt("my_agent_prompt"),
    "allowed_tools": [
        "Read", "Write", "Edit", "Bash", "Glob", "Grep"
    ]
}
```

3. Use in orchestrator:

```markdown
Task(agent="my_agent", task="Do something")
```

### Task 2: Customize Security Rules

Edit `security.py` to add allowed commands:

```python
ALLOWED_COMMANDS.add("my-tool")
ALLOWED_COMMANDS.add("another-command")

# Add validation for specific commands
def validate_my_tool(args: list[str]) -> ValidationResult:
    if "--dangerous-flag" in args:
        return ValidationResult(False, "Dangerous flag not allowed")
    return ValidationResult(True)
```

### Task 3: Add Custom Metrics

Create a metrics collector:

```python
from dashboard.metrics import MetricsCollector

collector = MetricsCollector()
collector.record_event("custom_event", {"data": "value"})
collector.save()
```

### Task 4: Integrate New AI Provider

1. Create bridge in `bridges/`:

```python
# bridges/my_provider_bridge.py
class MyProviderBridge:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def create_session(self, model: str) -> Session:
        return Session(model=model)

    def send_message(self, session: Session, message: str) -> Response:
        # Implementation
        pass
```

2. Add environment configuration
3. Create CLI tool in `scripts/`
4. Document in integration guide

### Task 5: Create Custom Prompt Template

1. Create template file:

```bash
cat > prompts/my_task.md << 'EOF'
# My Custom Task

You are working on project: {project_dir}

Your task is to:
1. First step
2. Second step
3. Third step

Context: {additional_context}
EOF
```

2. Load in code:

```python
from prompts import load_prompt

template = load_prompt("my_task")
prompt = template.format(
    project_dir="/path/to/project",
    additional_context="Some context"
)
```

## Testing Guide

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_security.py

# Run specific test
pytest tests/test_security.py::test_validate_bash_command
```

### Writing Tests

Example test structure:

```python
import pytest
from pathlib import Path
from client import create_client, create_security_settings

def test_create_security_settings():
    """Test security settings creation."""
    settings = create_security_settings()

    assert settings["sandbox"]["enabled"] is False
    assert settings["permissions"]["defaultMode"] == "acceptEdits"
    assert "Bash(*)" in settings["permissions"]["allow"]

@pytest.mark.asyncio
async def test_agent_session():
    """Test running an agent session."""
    project_dir = Path("./test-project")
    client = create_client(project_dir, "haiku")

    async with client:
        # Test implementation
        pass
```

### Integration Tests

```bash
# Run integration tests
pytest tests/test_integration*.py -v

# Run with Playwright
pytest tests/test_playwright_*.py --headed
```

## Security Considerations

### Defense in Depth

The system implements multiple security layers:

1. **OS Sandbox**: Bash commands run in isolated environment
2. **File Permissions**: Operations restricted to project directory
3. **Command Allowlist**: Only approved commands can execute
4. **Extra Validation**: Sensitive commands get additional checks

### Best Practices

1. **Never disable security hooks** in production
2. **Audit ALLOWED_COMMANDS** regularly
3. **Validate all user input** before passing to agents
4. **Use read-only mode** when possible
5. **Monitor agent actions** through logging

### Sensitive Command Handling

```python
# Dangerous commands require extra validation
COMMANDS_NEEDING_EXTRA_VALIDATION = {
    "pkill",    # Process termination
    "chmod",    # Permission changes
    "rm",       # File deletion
    "git",      # Version control
    "init.sh"   # Script execution
}
```

### API Key Management

```bash
# Never commit .env files
echo ".env" >> .gitignore

# Use environment-specific configurations
cp .env.example .env.development
cp .env.example .env.production

# Rotate keys regularly
# Use secrets management in production (AWS Secrets Manager, etc.)
```

## Additional Resources

- [API Documentation](api/index.html) - Generated API docs
- [Bridge Interface Documentation](BRIDGE_INTERFACE.md) - AI provider bridge specs
- [Architecture Diagrams](architecture/) - System architecture diagrams
- [Contributing Guide](../CONTRIBUTING.md) - How to contribute

## Support

For questions or issues:

1. Check the [API Documentation](api/index.html)
2. Search existing [GitHub Issues](https://github.com/your-org/agent-dashboard/issues)
3. Join the community Slack channel
4. Read the main [README.md](../README.md)

## Changelog

See [CHANGELOG.md](../CHANGELOG.md) for version history and updates.
