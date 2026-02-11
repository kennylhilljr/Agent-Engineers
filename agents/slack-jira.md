# Slack-to-Jira Bridge

A standalone service that lets Slack users create Jira issues via slash commands and message shortcuts.

## Location

All bridge code lives in `slack-jira-bridge/`:

```
slack-jira-bridge/
├── .env                    # Slack + Jira credentials (never commit!)
├── config.yaml             # Jira export configuration
├── requirements.txt        # Python dependencies
├── slack_jira_bridge.py    # Slack bot (slash command + modal)
└── export_all_issues.py    # Batch export all KAN issues to CSV/JSON
```

## Setup

### 1. Create a Slack App

1. Go to https://api.slack.com/apps -> Create New App -> From scratch
2. Name: "Jira Bridge", pick your workspace
3. **Enable Socket Mode**: Settings -> Socket Mode -> Enable. Generate an app-level token (`xapp-...`)
4. **OAuth & Permissions**: Add bot scopes: `commands`, `chat:write`, `chat:write.public`
5. **Slash Command**: Create `/jira-story` command
6. **Message Shortcut** (optional): Create "Create Jira Story" with callback ID `create_jira_story`
7. **Install to Workspace**: Copy the Bot User OAuth Token (`xoxb-...`)

### 2. Configure .env

Edit `slack-jira-bridge/.env` with your Slack tokens:

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-level-token
```

Jira credentials are already pre-configured from the project .env.

### 3. Run

```bash
cd slack-jira-bridge
source .venv/bin/activate
python slack_jira_bridge.py
```

### 4. Test in Slack

```
/jira-story Add search bar | Users need a global search bar on the dashboard
/jira-story Add login | OAuth login flow | priority=High labels=auth
```

## Jira Export Tool

To export all KAN issues to CSV + JSON:

```bash
cd slack-jira-bridge
source .venv/bin/activate
python export_all_issues.py
```

Output goes to `downloaded_issues/`.

## Integration with your-claude-engineer

The Slack-Jira bridge creates issues in the KAN project. The `jira` agent in your-claude-engineer picks up these issues and processes them through the orchestrator workflow:

1. User runs `/jira-story` in Slack -> creates Jira issue
2. Orchestrator asks `jira` agent for next issue -> picks up the new story
3. `coding` agent implements the feature
4. `jira` agent marks it Done with evidence
5. `slack` agent notifies `#ai-cli-macz` channel
