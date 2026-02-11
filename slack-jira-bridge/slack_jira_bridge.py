#!/usr/bin/env python3
"""
Slack -> Jira bridge:
  - Slash command `/jira-story` creates a new story in the KAN project.
  - Optional key/value flags let you set priority, labels, assignee, etc.
  - The bot replies with a clickable link and the issue key.
  - Message shortcut "Create Jira Story" provides a modal UI.
"""

import os
import re

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from jira import JIRA

# --------------------------------------------------------------
# Load environment variables
# --------------------------------------------------------------
load_dotenv()

# ----- Slack credentials -----
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
if not (SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET):
    raise RuntimeError("Missing Slack credentials in .env")

# ----- Jira credentials -----
JIRA_SERVER = os.getenv("JIRA_SERVER")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "KAN")
JIRA_ISSUE_TYPE = os.getenv("JIRA_ISSUE_TYPE", "Story")

jira = JIRA(
    server=JIRA_SERVER,
    basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN),
)


def parse_command_text(text: str):
    """
    Parse slash command text.
    Format: title | description
    Or:     title | description | priority=High labels=frontend,ui assignee=jdoe
    """
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 2:
        raise ValueError(
            "Please use the format `title | description` "
            "(you can add flags after a second `|`)."
        )
    summary, description = parts[0], parts[1]

    extra_fields = {}
    if len(parts) > 2:
        flag_str = parts[2]
        for token in re.split(r"\s+", flag_str):
            if "=" not in token:
                continue
            k, v = token.split("=", 1)
            k, v = k.lower(), v.strip()
            if k == "labels":
                extra_fields["labels"] = [lbl.strip() for lbl in v.split(",")]
            elif k == "priority":
                extra_fields["priority"] = {"name": v}
            elif k == "assignee":
                extra_fields["assignee"] = {"name": v}
            else:
                extra_fields[k] = v

    return {"summary": summary, "description": description, "extra": extra_fields}


# --------------------------------------------------------------
# Initialise the Bolt app (socket mode works behind firewalls)
# --------------------------------------------------------------
app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)


# --------------------------------------------------------------
# Slash command: /jira-story
# --------------------------------------------------------------
@app.command("/jira-story")
def handle_jira_story(ack, body, respond, logger):
    """
    Usage in Slack:
    /jira-story  My new feature | A short description of what it does
    /jira-story  My new feature | A short description | priority=High labels=frontend,ui
    """
    ack()

    user_id = body["user_id"]
    raw_text = body.get("text", "").strip()

    if not raw_text:
        respond(
            text="You forgot to add a title & description. Example:\n"
            "`/jira-story  Add search bar | Users need a global search bar`",
            response_type="ephemeral",
        )
        return

    try:
        parsed = parse_command_text(raw_text)
    except ValueError as e:
        respond(text=f"Error: {e}", response_type="ephemeral")
        return

    # Build the Jira payload
    jira_fields = {
        "project": {"key": JIRA_PROJECT_KEY},
        "summary": parsed["summary"],
        "description": parsed["description"],
        "issuetype": {"name": JIRA_ISSUE_TYPE},
    }
    jira_fields.update(parsed["extra"])

    try:
        new_issue = jira.create_issue(fields=jira_fields)
    except Exception as exc:
        logger.exception("Jira creation failed")
        respond(
            text=f"Failed to create issue in Jira: `{exc}`",
            response_type="ephemeral",
        )
        return

    issue_key = new_issue.key
    issue_url = f"{JIRA_SERVER}/browse/{issue_key}"
    issue_link_md = f"<{issue_url}|{issue_key}>"

    respond(
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Created {issue_link_md}*\n*Summary:* {parsed['summary']}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Requested by <@{user_id}>"}
                ],
            },
        ],
        response_type="in_channel",
    )


# --------------------------------------------------------------
# Message shortcut: "Create Jira Story" (right-click -> Apps)
# --------------------------------------------------------------
@app.shortcut("create_jira_story")
def open_modal(ack, shortcut, client, logger):
    """Shows a modal where the user can fill title/description/flags."""
    ack()
    trigger_id = shortcut["trigger_id"]
    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "jira_story_modal",
            "title": {"type": "plain_text", "text": "Create Jira Story"},
            "submit": {"type": "plain_text", "text": "Create"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "title_block",
                    "label": {"type": "plain_text", "text": "Title"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "title_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Short, punchy title",
                        },
                    },
                },
                {
                    "type": "input",
                    "block_id": "desc_block",
                    "label": {"type": "plain_text", "text": "Description"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "desc_input",
                        "multiline": True,
                    },
                },
                {
                    "type": "input",
                    "optional": True,
                    "block_id": "flags_block",
                    "label": {"type": "plain_text", "text": "Optional flags"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "flags_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "e.g. priority=High labels=frontend,ui assignee=jdoe",
                        },
                    },
                },
            ],
        },
    )


@app.view("jira_story_modal")
def handle_modal_submission(ack, body, view, client, logger):
    """When the user hits 'Create' in the modal."""
    user_id = body["user"]["id"]
    values = view["state"]["values"]
    title = values["title_block"]["title_input"]["value"]
    description = values["desc_block"]["desc_input"]["value"]
    raw_flags = (values["flags_block"]["flags_input"]["value"] or "").strip()

    command_text = f"{title} | {description}"
    if raw_flags:
        command_text += f" | {raw_flags}"

    try:
        parsed = parse_command_text(command_text)
    except ValueError as e:
        ack(response_action="errors", errors={"title_block": str(e)})
        return

    jira_fields = {
        "project": {"key": JIRA_PROJECT_KEY},
        "summary": parsed["summary"],
        "description": parsed["description"],
        "issuetype": {"name": JIRA_ISSUE_TYPE},
    }
    jira_fields.update(parsed["extra"])

    try:
        new_issue = jira.create_issue(fields=jira_fields)
    except Exception as exc:
        logger.exception("Jira creation failed")
        ack(
            response_action="errors",
            errors={"title_block": f"Jira error: {exc}"},
        )
        return

    ack()

    issue_key = new_issue.key
    issue_url = f"{JIRA_SERVER}/browse/{issue_key}"
    issue_link_md = f"<{issue_url}|{issue_key}>"

    # Post confirmation to the channel the shortcut was triggered from
    channel_id = body.get("channel", {}).get("id")
    if channel_id:
        client.chat_postMessage(
            channel=channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Created {issue_link_md}*\n*Summary:* {parsed['summary']}",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"Requested by <@{user_id}>"}
                    ],
                },
            ],
        )


# --------------------------------------------------------------
# Run the app in Socket Mode (no public URL needed)
# --------------------------------------------------------------
if __name__ == "__main__":
    app_token = os.getenv("SLACK_APP_TOKEN")
    if not app_token:
        raise RuntimeError(
            "You must set SLACK_APP_TOKEN (App-level token starting with xapp-) in .env"
        )
    print("Starting Slack-Jira bridge in Socket Mode...")
    SocketModeHandler(app, app_token).start()
