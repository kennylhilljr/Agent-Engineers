# Contributing to Agent Engineers

Thank you for your interest in contributing! This guide covers everything you need to get started.

## Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** for package management
- **Node.js/npm** (for Playwright and generated projects)
- **Claude CLI** authentication (`claude login`)

## Development Setup

```bash
# Clone the repository
git clone https://github.com/<org>/agent-engineers.git
cd agent-engineers

# Install dependencies and pre-commit hooks
make dev

# Copy environment template and configure
cp .env.example .env
# Edit .env with your API keys (see README for details)
```

## Running Tests

```bash
# Run all tests
make test

# Run a specific test file
uv run python -m pytest tests/test_tenant_isolation.py -v

# Run with coverage
uv run python -m pytest tests/ --cov
```

## Linting and Formatting

```bash
# Check for lint issues
make lint

# Auto-format code
make format

# Type checking
make typecheck
```

Pre-commit hooks run `ruff` and formatting checks automatically on each commit. To run them manually against all files:

```bash
pre-commit run --all-files
```

## Code Conventions

- **Type hints** on all function signatures
- **Async/await** for agent and I/O logic
- **Docstrings** on all public functions (Args/Returns/Raises)
- **Ruff** for linting and formatting (config in `pyproject.toml`, line-length 100)
- **Module-level logging** via `logging.getLogger(__name__)` — avoid bare `print()` in library code

## Adding a New Agent

1. Create a prompt file in `prompts/<name>_agent_prompt.md`
2. Add an `AgentDefinition` in `agents/definitions.py`
3. Define the tool subset in `scripts/arcade_config.py` (if using Arcade tools)
4. Add a `{NAME}_AGENT_MODEL` env var in the `_get_model()` function in `agents/model_routing.py`
5. Write tests in `tests/`

## Commit Conventions

Use clear, descriptive commit messages:

```
<type>: <short summary>

<optional body with context>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`

Examples:
- `feat: add SCIM provisioning endpoint`
- `fix: prevent context window exhaustion in long sessions`
- `test: add tenant isolation integration tests`

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with tests
3. Ensure all checks pass: `make lint && make test && make typecheck`
4. Open a PR using the provided template
5. Request review from the relevant code owners (see `CODEOWNERS`)
6. Address review feedback
7. Squash and merge once approved

## Security

This project uses defense-in-depth security (see `security.py`). If your change involves:

- New bash commands: add to `ALLOWED_COMMANDS` in `security.py`
- New API endpoints: ensure tenant isolation and authentication
- External integrations: follow the Arcade MCP gateway pattern

Run `make security-audit` to verify security hooks.

## Questions?

Open an issue or check existing documentation in `docs/`.
