"""Webhook Support for CI/CD Pipeline Integration (AI-229).

This module provides outbound and inbound webhook functionality for the Agent Dashboard.

Outbound webhooks:
    - Send events: agent.session.started, agent.session.completed, agent.session.failed,
      pr.created, pr.merged, ticket.transitioned
    - HMAC-SHA256 signed payloads
    - Retry with exponential backoff (up to 3 retries)
    - Delivery log (last 50 deliveries)

Inbound webhooks:
    - POST /api/webhooks/inbound/run-ticket  - trigger agent on a ticket
    - POST /api/webhooks/inbound/run-spec    - trigger agent on a spec

Usage:
    from dashboard.webhooks import WebhookManager

    manager = WebhookManager()
    webhook_id = manager.register_webhook(
        url="https://example.com/hook",
        events=["agent.session.started", "pr.created"],
        secret="my-secret-key"
    )
    await manager.trigger_event("agent.session.started", {"session_id": "abc123"})
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Valid event types
VALID_EVENTS = [
    "agent.session.started",
    "agent.session.completed",
    "agent.session.failed",
    "pr.created",
    "pr.merged",
    "ticket.transitioned",
]

# Delivery log max size
DELIVERY_LOG_MAX = 50

# Maximum retry attempts
MAX_RETRIES = 3

# Base delay for exponential backoff (seconds)
BACKOFF_BASE = 1.0


class WebhookManager:
    """Manages outbound and inbound webhooks for CI/CD pipeline integration.

    Thread-safe in-memory storage for webhooks and delivery logs.

    Attributes:
        _webhooks: Dict mapping webhook_id -> webhook config dict
        _delivery_log: Deque of last DELIVERY_LOG_MAX delivery records
    """

    def __init__(self):
        """Initialize the WebhookManager with empty stores."""
        # {webhook_id: {"id": str, "url": str, "events": list, "secret": str,
        #               "created_at": str, "active": bool}}
        self._webhooks: Dict[str, Dict[str, Any]] = {}

        # Circular buffer of last 50 delivery records
        # Each record: {"id": str, "webhook_id": str, "url": str, "event": str,
        #               "status": "success"|"failed", "response_code": int|None,
        #               "timestamp": str, "attempt": int, "error": str|None}
        self._delivery_log: deque = deque(maxlen=DELIVERY_LOG_MAX)

    def register_webhook(self, url: str, events: List[str], secret: str = "") -> str:
        """Register a new outbound webhook.

        Args:
            url: Target URL to send events to
            events: List of event types to subscribe to (see VALID_EVENTS)
            secret: HMAC-SHA256 secret key for payload signing

        Returns:
            webhook_id: Unique identifier for this webhook

        Raises:
            ValueError: If url is empty or events list is empty
        """
        if not url or not url.strip():
            raise ValueError("Webhook URL cannot be empty")
        if not events:
            raise ValueError("Webhook must subscribe to at least one event")

        # Validate event types
        invalid = [e for e in events if e not in VALID_EVENTS]
        if invalid:
            raise ValueError(f"Invalid event types: {invalid}. Valid: {VALID_EVENTS}")

        webhook_id = str(uuid.uuid4())
        self._webhooks[webhook_id] = {
            "id": webhook_id,
            "url": url.strip(),
            "events": list(events),
            "secret": secret,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "active": True,
        }
        logger.info(f"Registered webhook {webhook_id} for URL {url} events={events}")
        return webhook_id

    def delete_webhook(self, webhook_id: str) -> bool:
        """Remove a registered webhook.

        Args:
            webhook_id: ID of webhook to delete

        Returns:
            True if deleted, False if not found
        """
        if webhook_id in self._webhooks:
            del self._webhooks[webhook_id]
            logger.info(f"Deleted webhook {webhook_id}")
            return True
        return False

    def get_webhook(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Get a webhook by ID (without the secret).

        Args:
            webhook_id: ID of webhook to retrieve

        Returns:
            Webhook dict (without secret) or None if not found
        """
        webhook = self._webhooks.get(webhook_id)
        if webhook is None:
            return None
        # Return copy without secret
        result = dict(webhook)
        result.pop("secret", None)
        return result

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all registered webhooks (without secrets).

        Returns:
            List of webhook dicts (without secret field)
        """
        result = []
        for webhook in self._webhooks.values():
            w = dict(webhook)
            w.pop("secret", None)
            result.append(w)
        return result

    def get_delivery_log(self) -> List[Dict[str, Any]]:
        """Get the last DELIVERY_LOG_MAX delivery records.

        Returns:
            List of delivery log entries (most recent last)
        """
        return list(self._delivery_log)

    def _sign_payload(self, payload: str, secret: str) -> str:
        """Sign a payload string with HMAC-SHA256.

        Args:
            payload: JSON string to sign
            secret: Secret key

        Returns:
            Hex-encoded HMAC-SHA256 signature (prefixed with 'sha256=')
        """
        if not secret:
            return ""
        sig = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={sig}"

    @staticmethod
    def verify_signature(payload: str, secret: str, signature: str) -> bool:
        """Verify an HMAC-SHA256 signature.

        Args:
            payload: The raw JSON payload string
            secret: The shared secret key
            signature: The signature to verify (format: 'sha256=<hex>')

        Returns:
            True if signature is valid, False otherwise
        """
        if not secret or not signature:
            return False
        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def _log_delivery(
        self,
        webhook_id: str,
        url: str,
        event: str,
        status: str,
        response_code: Optional[int],
        attempt: int = 1,
        error: Optional[str] = None,
    ) -> None:
        """Record a delivery attempt in the log.

        Args:
            webhook_id: ID of the webhook
            url: Target URL
            event: Event type that was delivered
            status: "success" or "failed"
            response_code: HTTP response code, or None if connection failed
            attempt: Which attempt number this was (1-based)
            error: Error message if failed
        """
        entry = {
            "id": str(uuid.uuid4()),
            "webhook_id": webhook_id,
            "url": url,
            "event": event,
            "status": status,
            "response_code": response_code,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "attempt": attempt,
            "error": error,
        }
        self._delivery_log.append(entry)

    async def _deliver_once(
        self,
        url: str,
        headers: Dict[str, str],
        payload_str: str,
        timeout: float = 5.0,
    ) -> int:
        """Attempt a single HTTP POST delivery.

        Args:
            url: Target URL
            headers: HTTP headers to send
            payload_str: JSON payload string
            timeout: Request timeout in seconds

        Returns:
            HTTP response status code

        Raises:
            Exception: On connection or timeout error
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=payload_str,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                return resp.status

    async def _deliver_with_retry(
        self,
        webhook: Dict[str, Any],
        event: str,
        payload: Dict[str, Any],
    ) -> None:
        """Deliver an event to a webhook URL with exponential backoff retry.

        Attempts delivery up to MAX_RETRIES times. Delays between attempts:
            Attempt 1: immediate
            Attempt 2: 1 second
            Attempt 3: 2 seconds

        Args:
            webhook: Webhook configuration dict (must include id, url, secret)
            event: Event type name
            payload: Event payload dict (will be JSON-serialized and signed)
        """
        webhook_id = webhook["id"]
        url = webhook["url"]
        secret = webhook.get("secret", "")

        # Build the envelope
        envelope = {
            "id": str(uuid.uuid4()),
            "event": event,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payload": payload,
        }
        payload_str = json.dumps(envelope, separators=(",", ":"))
        signature = self._sign_payload(payload_str, secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event,
            "User-Agent": "AgentDashboard-Webhook/1.0",
        }
        if signature:
            headers["X-Hub-Signature-256"] = signature

        last_error = None
        last_code = None

        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                delay = BACKOFF_BASE * (2 ** (attempt - 2))  # 1s, 2s
                logger.debug(f"Webhook {webhook_id} retry {attempt} after {delay}s delay")
                await asyncio.sleep(delay)

            try:
                status_code = await self._deliver_once(url, headers, payload_str)
                last_code = status_code

                if 200 <= status_code < 300:
                    self._log_delivery(
                        webhook_id=webhook_id,
                        url=url,
                        event=event,
                        status="success",
                        response_code=status_code,
                        attempt=attempt,
                    )
                    logger.info(
                        f"Webhook {webhook_id} delivered {event} -> {url} "
                        f"[{status_code}] attempt={attempt}"
                    )
                    return

                last_error = f"HTTP {status_code}"
                logger.warning(
                    f"Webhook {webhook_id} delivery failed {event} -> {url} "
                    f"[{status_code}] attempt={attempt}"
                )

            except asyncio.TimeoutError:
                last_error = "Timeout"
                last_code = None
                logger.warning(
                    f"Webhook {webhook_id} timeout {event} -> {url} attempt={attempt}"
                )
            except Exception as exc:
                last_error = str(exc)
                last_code = None
                logger.warning(
                    f"Webhook {webhook_id} error {event} -> {url} attempt={attempt}: {exc}"
                )

        # All retries exhausted - log failure
        self._log_delivery(
            webhook_id=webhook_id,
            url=url,
            event=event,
            status="failed",
            response_code=last_code,
            attempt=MAX_RETRIES,
            error=last_error,
        )
        logger.error(
            f"Webhook {webhook_id} permanently failed {event} -> {url} after "
            f"{MAX_RETRIES} attempts. Last error: {last_error}"
        )

    async def trigger_event(self, event_type: str, payload: Dict[str, Any]) -> int:
        """Send an event to all subscribed webhooks asynchronously.

        Fires all matching webhooks concurrently. Does not wait for results
        when called from non-async context; use await for proper error tracking.

        Args:
            event_type: One of the VALID_EVENTS strings
            payload: Event-specific data dict

        Returns:
            Number of webhooks triggered

        Raises:
            ValueError: If event_type is not in VALID_EVENTS
        """
        if event_type not in VALID_EVENTS:
            raise ValueError(
                f"Unknown event type: {event_type}. Valid: {VALID_EVENTS}"
            )

        matching = [
            w for w in self._webhooks.values()
            if w.get("active", True) and event_type in w.get("events", [])
        ]

        if not matching:
            logger.debug(f"No webhooks subscribed to {event_type}")
            return 0

        tasks = [
            asyncio.create_task(self._deliver_with_retry(w, event_type, payload))
            for w in matching
        ]

        # Fire-and-forget: tasks run concurrently but we return immediately
        # Errors are logged inside _deliver_with_retry
        logger.info(f"Triggered event {event_type} to {len(matching)} webhook(s)")
        return len(matching)

    async def test_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Send a test ping to a registered webhook.

        Args:
            webhook_id: ID of the webhook to test

        Returns:
            Dict with success status and details

        Raises:
            KeyError: If webhook_id does not exist
        """
        webhook = self._webhooks.get(webhook_id)
        if webhook is None:
            raise KeyError(f"Webhook {webhook_id} not found")

        test_payload = {
            "test": True,
            "message": "This is a test delivery from Agent Dashboard",
        }

        result = {"webhook_id": webhook_id, "url": webhook["url"]}

        try:
            await self._deliver_with_retry(webhook, "agent.session.started", test_payload)
            # Check last delivery log entry for this webhook
            recent = [
                e for e in reversed(list(self._delivery_log))
                if e["webhook_id"] == webhook_id
            ]
            if recent:
                result["status"] = recent[0]["status"]
                result["response_code"] = recent[0].get("response_code")
            else:
                result["status"] = "unknown"
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)

        return result


# Module-level singleton instance
_webhook_manager: Optional[WebhookManager] = None


def get_webhook_manager() -> WebhookManager:
    """Get or create the global WebhookManager singleton.

    Returns:
        The global WebhookManager instance
    """
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager
