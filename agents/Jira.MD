# Jira Agent

The Jira agent manages Jira issues and project tracking as an alternative to the Linear agent. It uses the Jira Cloud REST API v3 via curl commands.

## Setup

### 1. Get a Jira API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Copy the token

### 2. Configure Environment

Add these to your `.env` file:

```bash
JIRA_SERVER=https://yourorg.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
JIRA_PROJECT_KEY=KAN
JIRA_AGENT_MODEL=haiku  # optional: haiku, sonnet, opus
```

### 3. Verify Connection

```bash
curl -s "https://yourorg.atlassian.net/rest/api/3/myself" \
  -H "Authorization: Basic $(echo -n 'email:token' | base64)"
```

## Architecture

The Jira agent follows the same multi-agent pattern as the Linear agent:

- **Agent definition**: `agents/definitions.py` → `JIRA_AGENT`
- **System prompt**: `prompts/jira_agent_prompt.md`
- **State file**: `.jira_project.json` (per project)
- **Tools**: `Read`, `Write`, `Edit`, `Bash` (for curl API calls)

## Using Jira Instead of Linear

To use Jira instead of Linear for project management, update the orchestrator prompt (`prompts/orchestrator_prompt.md`) to reference the `jira` agent instead of `linear` for issue tracking operations.

## Capabilities

| Operation | API Endpoint |
|-----------|-------------|
| Search issues | `GET /rest/api/3/search?jql=...` |
| Get issue | `GET /rest/api/3/issue/{key}` |
| Create issue | `POST /rest/api/3/issue` |
| Update issue | `PUT /rest/api/3/issue/{key}` |
| Transition issue | `POST /rest/api/3/issue/{key}/transitions` |
| Add comment | `POST /rest/api/3/issue/{key}/comment` |
| List projects | `GET /rest/api/3/project` |

## Original Reference

The original standalone Jira automation framework (before integration into Agent-Engineers) is archived at `docs/jira_standalone_reference.md`.
