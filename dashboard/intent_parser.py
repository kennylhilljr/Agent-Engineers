"""Intent Parser - Parse user chat messages to detect agent-action intents.

This module analyzes user messages to determine:
- Whether the message requires an agent action, a query, or a conversation
- Which agent (if any) should handle the request
- What parameters are needed for the action

Intent Types:
    agent_action: Requires delegation to a specific agent
    query: A query that can be answered from Linear/knowledge base
    conversation: General conversation handled by AI provider
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedIntent:
    """Result of parsing a user message.

    Attributes:
        intent_type: One of "agent_action", "query", or "conversation"
        agent: The target agent name (e.g., "linear", "coding", "github"), or None
        action: The action to perform (e.g., "status", "start", "pause", "resume")
        params: Additional parameters extracted from the message
        original_message: The original user message
    """
    intent_type: str  # "agent_action" | "query" | "conversation"
    agent: Optional[str]
    action: Optional[str]
    params: dict = field(default_factory=dict)
    original_message: str = ""


# Ticket key pattern: e.g., AI-1, AI-109, PROJ-42
TICKET_PATTERN = re.compile(r'\b([A-Z]+-\d+)\b')

# Known agents
KNOWN_AGENTS = {
    "linear", "coding", "github", "slack",
    "pr_reviewer", "ops", "coding_fast", "pr_reviewer_fast",
    "chatgpt", "gemini", "groq", "kimi", "windsurf"
}

# Status query patterns
STATUS_PATTERNS = [
    # "What is AI-1 status?" / "What's AI-109 status?"
    re.compile(
        r"what(?:'s|is|\s+is)\s+(?:the\s+)?([A-Z]+-\d+)\s+status",
        re.IGNORECASE
    ),
    # "status of AI-1" / "status for AI-109"
    re.compile(
        r"status\s+(?:of|for)\s+([A-Z]+-\d+)",
        re.IGNORECASE
    ),
    # "check AI-1" / "check status AI-1"
    re.compile(
        r"check(?:\s+status(?:\s+of)?)?\s+([A-Z]+-\d+)",
        re.IGNORECASE
    ),
    # "status [ticket]" as a command
    re.compile(
        r"^status\s+([A-Z]+-\d+)\s*$",
        re.IGNORECASE
    ),
    # "show AI-1" / "show me AI-1"
    re.compile(
        r"show(?:\s+me)?\s+([A-Z]+-\d+)",
        re.IGNORECASE
    ),
    # "get AI-1" / "get status AI-1"
    re.compile(
        r"get(?:\s+(?:the\s+)?status\s+(?:of\s+)?)?\s+([A-Z]+-\d+)",
        re.IGNORECASE
    ),
    # "AI-1 status"
    re.compile(
        r"([A-Z]+-\d+)\s+status",
        re.IGNORECASE
    ),
]

# Start agent patterns: "Start [agent] on [ticket]" / "Run [agent] on [ticket]"
START_PATTERNS = [
    re.compile(
        r"(?:start|run|launch|kick\s*off)\s+([\w_]+)\s+(?:on|for|with)\s+([A-Z]+-\d+)",
        re.IGNORECASE
    ),
    re.compile(
        r"(?:start|run|launch|kick\s*off)\s+([\w_]+)\s+([A-Z]+-\d+)",
        re.IGNORECASE
    ),
    re.compile(
        r"(?:start|run|execute|assign)\s+([\w_]+)\s+agent(?:\s+on\s+|\s+for\s+|\s+with\s+)([A-Z]+-\d+)",
        re.IGNORECASE
    ),
]

# Pause agent patterns
PAUSE_PATTERNS = [
    re.compile(
        r"(?:pause|stop|halt)\s+([\w_]+)(?:\s+agent)?",
        re.IGNORECASE
    ),
]

# Resume agent patterns
RESUME_PATTERNS = [
    re.compile(
        r"(?:resume|restart|continue)\s+([\w_]+)(?:\s+agent)?",
        re.IGNORECASE
    ),
]

# GitHub query patterns — route to the github agent
GITHUB_PATTERNS = [
    re.compile(r"(?:list|show|what|get)\s+(?:are\s+)?(?:the\s+)?(?:all\s+)?(?:open\s+)?(?:PRs?|pull\s*requests?)", re.IGNORECASE),
    re.compile(r"(?:open|merged|closed)\s+(?:PRs?|pull\s*requests?)", re.IGNORECASE),
    re.compile(r"(?:list|show|what|get)\s+(?:are\s+)?(?:the\s+)?(?:all\s+)?(?:branches|commits|releases|tags)", re.IGNORECASE),
    re.compile(r"(?:PR|pull\s*request)\s*#?\d+", re.IGNORECASE),
    re.compile(r"(?:merge|review|approve|close)\s+(?:PR|pull\s*request)", re.IGNORECASE),
]

# List/query patterns that can be answered without agent action
QUERY_PATTERNS = [
    re.compile(r"(?:list|show)\s+(?:all\s+)?(?:open\s+)?(?:issues?|tickets?)", re.IGNORECASE),
    re.compile(r"(?:what|which)\s+(?:agents?|issues?|tickets?)\s+(?:are|is)\s+(?:available|active|running)", re.IGNORECASE),
    re.compile(r"how\s+many\s+(?:agents?|issues?|tickets?)", re.IGNORECASE),
    re.compile(r"(?:list|show)\s+(?:all\s+)?agents?", re.IGNORECASE),
]


def parse_intent(message: str) -> ParsedIntent:
    """Parse a user message to detect the intent.

    Args:
        message: The raw user message text

    Returns:
        ParsedIntent with intent_type, agent, action, and params
    """
    msg = message.strip()

    if not msg:
        return ParsedIntent(
            intent_type="conversation",
            agent=None,
            action=None,
            params={},
            original_message=message
        )

    # 1. Check for status query patterns
    for pattern in STATUS_PATTERNS:
        match = pattern.search(msg)
        if match:
            ticket = match.group(1).upper()
            return ParsedIntent(
                intent_type="agent_action",
                agent="linear",
                action="status",
                params={"ticket": ticket},
                original_message=message
            )

    # 2. Check for start/run agent patterns
    for pattern in START_PATTERNS:
        match = pattern.search(msg)
        if match:
            agent_name = match.group(1).lower().replace("-", "_")
            ticket = match.group(2).upper()
            # Validate agent name
            if agent_name not in KNOWN_AGENTS:
                # Try to find closest agent name
                agent_name = _find_closest_agent(agent_name) or agent_name
            return ParsedIntent(
                intent_type="agent_action",
                agent=agent_name,
                action="start",
                params={"ticket": ticket, "target_agent": agent_name},
                original_message=message
            )

    # 3. Check for pause patterns
    for pattern in PAUSE_PATTERNS:
        match = pattern.search(msg)
        if match:
            agent_name = match.group(1).lower().replace("-", "_")
            if agent_name in KNOWN_AGENTS or _find_closest_agent(agent_name):
                resolved = _find_closest_agent(agent_name) or agent_name
                return ParsedIntent(
                    intent_type="agent_action",
                    agent=resolved,
                    action="pause",
                    params={"target_agent": resolved},
                    original_message=message
                )

    # 4. Check for resume patterns
    for pattern in RESUME_PATTERNS:
        match = pattern.search(msg)
        if match:
            agent_name = match.group(1).lower().replace("-", "_")
            if agent_name in KNOWN_AGENTS or _find_closest_agent(agent_name):
                resolved = _find_closest_agent(agent_name) or agent_name
                return ParsedIntent(
                    intent_type="agent_action",
                    agent=resolved,
                    action="resume",
                    params={"target_agent": resolved},
                    original_message=message
                )

    # 5. Check for bare ticket reference with implicit status intent
    # e.g., "AI-109" or "what about AI-109?"
    ticket_match = TICKET_PATTERN.search(msg)
    if ticket_match:
        lower_msg = msg.lower()
        # If message is primarily about the ticket, route to linear agent
        if any(kw in lower_msg for kw in ["status", "what", "tell me", "info", "about", "show"]):
            ticket = ticket_match.group(1).upper()
            return ParsedIntent(
                intent_type="agent_action",
                agent="linear",
                action="status",
                params={"ticket": ticket},
                original_message=message
            )
        # If just a bare ticket key or minimal context, still query it
        cleaned = TICKET_PATTERN.sub("", msg).strip().lower()
        if len(cleaned) <= 5:  # Very short remaining text = likely just the ticket
            ticket = ticket_match.group(1).upper()
            return ParsedIntent(
                intent_type="query",
                agent="linear",
                action="status",
                params={"ticket": ticket},
                original_message=message
            )

    # 6. Check for GitHub query patterns (route to github agent)
    for pattern in GITHUB_PATTERNS:
        match = pattern.search(msg)
        if match:
            return ParsedIntent(
                intent_type="agent_action",
                agent="github",
                action="query",
                params={"query": msg},
                original_message=message
            )

    # 7. Check for general query patterns
    for pattern in QUERY_PATTERNS:
        if pattern.search(msg):
            return ParsedIntent(
                intent_type="query",
                agent=None,
                action="list",
                params={},
                original_message=message
            )

    # 8. Default to conversation
    return ParsedIntent(
        intent_type="conversation",
        agent=None,
        action=None,
        params={},
        original_message=message
    )


def _find_closest_agent(name: str) -> Optional[str]:
    """Find the closest known agent name using substring matching.

    Args:
        name: Agent name to look up

    Returns:
        Matched agent name or None
    """
    name = name.lower().strip()

    # Direct match
    if name in KNOWN_AGENTS:
        return name

    # Substring match (e.g., "cod" -> "coding")
    matches = [a for a in KNOWN_AGENTS if name in a or a in name]
    if len(matches) == 1:
        return matches[0]

    # Common aliases
    aliases = {
        "code": "coding",
        "coder": "coding",
        "git": "github",
        "gh": "github",
        "gpt": "chatgpt",
        "openai": "chatgpt",
        "google": "gemini",
        "moonshot": "kimi",
        "cascade": "windsurf",
        "fast": "coding_fast",
        "pr": "pr_reviewer",
        "review": "pr_reviewer",
        "reviewer": "pr_reviewer",
        "lin": "linear",
        "ops": "ops",
        "slack": "slack",
    }

    return aliases.get(name)
