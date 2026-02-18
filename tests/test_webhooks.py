"""Tests for AI-229: Webhook Support for CI/CD Pipeline Integration.

Tests webhook registration, HMAC-SHA256 signing, delivery logging,
retry logic, inbound webhook endpoints, and the REST API endpoints.
"""

import asyncio
import hashlib
import hmac
import json
import tempfile
import uuid
from collections import deque
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import AioHTTPTestCase, TestClient

# Ensure the project root is in sys.path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.webhooks import (
    WebhookManager,
    get_webhook_manager,
    VALID_EVENTS,
    DELIVERY_LOG_MAX,
    MAX_RETRIES,
)


# ---------------------------------------------------------------------------
# Unit Tests: WebhookManager
# ---------------------------------------------------------------------------

class TestWebhookManagerRegistration:
    """Tests for webhook registration and listing."""

    def test_register_webhook_returns_id(self):
        """register_webhook returns a non-empty string UUID."""
        manager = WebhookManager()
        wid = manager.register_webhook(
            url="https://example.com/hook",
            events=["agent.session.started"],
        )
        assert isinstance(wid, str)
        assert len(wid) > 0

    def test_register_webhook_stores_url_and_events(self):
        """Registered webhook is retrievable with correct URL and events."""
        manager = WebhookManager()
        url = "https://example.com/hook"
        events = ["agent.session.started", "pr.created"]
        wid = manager.register_webhook(url=url, events=events, secret="s3cr3t")
        wh = manager.get_webhook(wid)
        assert wh is not None
        assert wh["url"] == url
        assert wh["events"] == events
        assert wh["active"] is True

    def test_register_webhook_does_not_expose_secret(self):
        """get_webhook() does not expose the secret field."""
        manager = WebhookManager()
        wid = manager.register_webhook(
            url="https://example.com/hook",
            events=["pr.merged"],
            secret="top-secret",
        )
        wh = manager.get_webhook(wid)
        assert "secret" not in wh

    def test_register_webhook_empty_url_raises(self):
        """Registering with empty URL raises ValueError."""
        manager = WebhookManager()
        with pytest.raises(ValueError, match="URL cannot be empty"):
            manager.register_webhook(url="", events=["pr.merged"])

    def test_register_webhook_empty_events_raises(self):
        """Registering with empty events list raises ValueError."""
        manager = WebhookManager()
        with pytest.raises(ValueError, match="at least one event"):
            manager.register_webhook(url="https://example.com", events=[])

    def test_register_webhook_invalid_event_raises(self):
        """Registering with invalid event type raises ValueError."""
        manager = WebhookManager()
        with pytest.raises(ValueError, match="Invalid event types"):
            manager.register_webhook(url="https://ex.com", events=["not.a.valid.event"])

    def test_list_webhooks_empty(self):
        """list_webhooks returns empty list when no webhooks registered."""
        manager = WebhookManager()
        assert manager.list_webhooks() == []

    def test_list_webhooks_returns_all(self):
        """list_webhooks returns all registered webhooks."""
        manager = WebhookManager()
        manager.register_webhook("https://a.com/h", ["pr.merged"])
        manager.register_webhook("https://b.com/h", ["pr.created"])
        webhooks = manager.list_webhooks()
        assert len(webhooks) == 2

    def test_list_webhooks_no_secret_field(self):
        """list_webhooks does not include secret in any webhook."""
        manager = WebhookManager()
        manager.register_webhook("https://a.com", ["pr.merged"], secret="my-secret")
        for wh in manager.list_webhooks():
            assert "secret" not in wh

    def test_get_webhook_returns_none_for_missing(self):
        """get_webhook returns None for a non-existent ID."""
        manager = WebhookManager()
        assert manager.get_webhook("nonexistent-id") is None

    def test_unique_ids(self):
        """Each webhook gets a unique ID."""
        manager = WebhookManager()
        id1 = manager.register_webhook("https://a.com", ["pr.merged"])
        id2 = manager.register_webhook("https://b.com", ["pr.merged"])
        assert id1 != id2


class TestWebhookManagerDeletion:
    """Tests for webhook deletion."""

    def test_delete_existing_webhook(self):
        """delete_webhook removes an existing webhook and returns True."""
        manager = WebhookManager()
        wid = manager.register_webhook("https://a.com", ["pr.merged"])
        assert manager.delete_webhook(wid) is True
        assert manager.get_webhook(wid) is None

    def test_delete_nonexistent_webhook(self):
        """delete_webhook returns False for non-existent webhook ID."""
        manager = WebhookManager()
        assert manager.delete_webhook("fake-id") is False

    def test_delete_reduces_list_count(self):
        """Deleted webhook no longer appears in list_webhooks."""
        manager = WebhookManager()
        w1 = manager.register_webhook("https://a.com", ["pr.merged"])
        manager.register_webhook("https://b.com", ["pr.created"])
        manager.delete_webhook(w1)
        webhooks = manager.list_webhooks()
        assert len(webhooks) == 1
        assert all(w["id"] != w1 for w in webhooks)


class TestHMACSigning:
    """Tests for HMAC-SHA256 payload signing."""

    def test_sign_payload_returns_sha256_prefix(self):
        """_sign_payload returns a signature starting with 'sha256='."""
        manager = WebhookManager()
        sig = manager._sign_payload('{"test": true}', "mysecret")
        assert sig.startswith("sha256=")

    def test_sign_payload_empty_secret_returns_empty(self):
        """_sign_payload returns empty string when no secret provided."""
        manager = WebhookManager()
        sig = manager._sign_payload('{"test": true}', "")
        assert sig == ""

    def test_sign_payload_is_deterministic(self):
        """Same payload and secret always produce the same signature."""
        manager = WebhookManager()
        payload = '{"event": "pr.created", "id": "123"}'
        secret = "my-secret-key"
        sig1 = manager._sign_payload(payload, secret)
        sig2 = manager._sign_payload(payload, secret)
        assert sig1 == sig2

    def test_sign_payload_different_secrets_differ(self):
        """Different secrets produce different signatures."""
        manager = WebhookManager()
        payload = '{"event": "pr.created"}'
        sig1 = manager._sign_payload(payload, "secret1")
        sig2 = manager._sign_payload(payload, "secret2")
        assert sig1 != sig2

    def test_sign_payload_different_payloads_differ(self):
        """Different payloads with the same secret produce different signatures."""
        manager = WebhookManager()
        secret = "same-secret"
        sig1 = manager._sign_payload('{"a": 1}', secret)
        sig2 = manager._sign_payload('{"a": 2}', secret)
        assert sig1 != sig2

    def test_verify_signature_valid(self):
        """verify_signature returns True for a correctly signed payload."""
        manager = WebhookManager()
        payload = '{"event": "agent.session.started"}'
        secret = "my-secret"
        sig = manager._sign_payload(payload, secret)
        assert WebhookManager.verify_signature(payload, secret, sig) is True

    def test_verify_signature_invalid(self):
        """verify_signature returns False for a tampered payload."""
        manager = WebhookManager()
        payload = '{"event": "agent.session.started"}'
        secret = "my-secret"
        # Sign with wrong secret
        wrong_sig = manager._sign_payload(payload, "wrong-secret")
        assert WebhookManager.verify_signature(payload, secret, wrong_sig) is False

    def test_verify_signature_empty_secret(self):
        """verify_signature returns False when no secret is provided."""
        assert WebhookManager.verify_signature('{"a": 1}', "", "sha256=abc") is False

    def test_sign_payload_matches_hmac_sha256(self):
        """_sign_payload produces correct HMAC-SHA256 independently verified."""
        manager = WebhookManager()
        payload = '{"test": "data"}'
        secret = "test-secret"
        expected_hex = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        sig = manager._sign_payload(payload, secret)
        assert sig == f"sha256={expected_hex}"


class TestDeliveryLog:
    """Tests for delivery logging."""

    def test_delivery_log_empty_initially(self):
        """Delivery log is empty at initialization."""
        manager = WebhookManager()
        assert manager.get_delivery_log() == []

    def test_log_delivery_adds_entry(self):
        """_log_delivery adds a record to the delivery log."""
        manager = WebhookManager()
        manager._log_delivery(
            webhook_id="wh-1",
            url="https://example.com",
            event="pr.merged",
            status="success",
            response_code=200,
            attempt=1,
        )
        log = manager.get_delivery_log()
        assert len(log) == 1
        entry = log[0]
        assert entry["webhook_id"] == "wh-1"
        assert entry["url"] == "https://example.com"
        assert entry["event"] == "pr.merged"
        assert entry["status"] == "success"
        assert entry["response_code"] == 200

    def test_delivery_log_max_size(self):
        """Delivery log does not exceed DELIVERY_LOG_MAX entries."""
        manager = WebhookManager()
        for i in range(DELIVERY_LOG_MAX + 10):
            manager._log_delivery(
                webhook_id=f"wh-{i}",
                url="https://example.com",
                event="pr.merged",
                status="success",
                response_code=200,
            )
        assert len(manager.get_delivery_log()) <= DELIVERY_LOG_MAX

    def test_delivery_log_contains_timestamp(self):
        """Each delivery log entry contains a timestamp."""
        manager = WebhookManager()
        manager._log_delivery(
            webhook_id="wh-1",
            url="https://example.com",
            event="pr.created",
            status="failed",
            response_code=500,
        )
        log = manager.get_delivery_log()
        assert "timestamp" in log[0]
        assert log[0]["timestamp"].endswith("Z")

    def test_delivery_log_contains_unique_ids(self):
        """Each delivery log entry has a unique ID."""
        manager = WebhookManager()
        for i in range(5):
            manager._log_delivery(
                webhook_id="wh-1",
                url="https://example.com",
                event="pr.merged",
                status="success",
                response_code=200,
            )
        log = manager.get_delivery_log()
        ids = [e["id"] for e in log]
        assert len(ids) == len(set(ids))


class TestTriggerEvent:
    """Tests for event triggering."""

    @pytest.mark.asyncio
    async def test_trigger_event_no_matching_webhooks(self):
        """trigger_event returns 0 when no webhooks match the event."""
        manager = WebhookManager()
        count = await manager.trigger_event("pr.merged", {"pr_id": 1})
        assert count == 0

    @pytest.mark.asyncio
    async def test_trigger_event_invalid_type_raises(self):
        """trigger_event raises ValueError for unknown event type."""
        manager = WebhookManager()
        with pytest.raises(ValueError, match="Unknown event type"):
            await manager.trigger_event("invalid.event", {})

    @pytest.mark.asyncio
    async def test_trigger_event_returns_matching_count(self):
        """trigger_event returns the number of matching webhooks."""
        manager = WebhookManager()
        manager.register_webhook("https://a.com", ["pr.merged"])
        manager.register_webhook("https://b.com", ["pr.merged", "pr.created"])
        manager.register_webhook("https://c.com", ["pr.created"])  # no match

        with patch.object(manager, "_deliver_with_retry", new_callable=AsyncMock):
            count = await manager.trigger_event("pr.merged", {"pr_id": 42})

        assert count == 2

    @pytest.mark.asyncio
    async def test_trigger_event_skips_inactive_webhooks(self):
        """trigger_event skips webhooks marked as inactive."""
        manager = WebhookManager()
        wid = manager.register_webhook("https://a.com", ["pr.merged"])
        manager._webhooks[wid]["active"] = False

        with patch.object(manager, "_deliver_with_retry", new_callable=AsyncMock) as mock_deliver:
            count = await manager.trigger_event("pr.merged", {})

        assert count == 0
        mock_deliver.assert_not_called()

    def test_valid_events_list_contains_required_events(self):
        """VALID_EVENTS contains all required event types."""
        required = [
            "agent.session.started",
            "agent.session.completed",
            "agent.session.failed",
            "pr.created",
            "pr.merged",
            "ticket.transitioned",
        ]
        for event in required:
            assert event in VALID_EVENTS


class TestRetryLogic:
    """Tests for delivery retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_deliver_with_retry_success_on_first_attempt(self):
        """Successful delivery on first attempt logs success with attempt=1."""
        manager = WebhookManager()
        wid = manager.register_webhook("https://example.com", ["pr.merged"], secret="s")
        webhook = manager._webhooks[wid]

        with patch.object(manager, "_deliver_once", new_callable=AsyncMock, return_value=200):
            await manager._deliver_with_retry(webhook, "pr.merged", {"pr": 1})

        log = manager.get_delivery_log()
        assert len(log) == 1
        assert log[0]["status"] == "success"
        assert log[0]["attempt"] == 1

    @pytest.mark.asyncio
    async def test_deliver_with_retry_success_on_second_attempt(self):
        """Delivery succeeds on second attempt after first failure."""
        manager = WebhookManager()
        wid = manager.register_webhook("https://example.com", ["pr.merged"])
        webhook = manager._webhooks[wid]

        call_count = 0

        async def mock_deliver(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Connection refused")
            return 200

        with patch.object(manager, "_deliver_once", side_effect=mock_deliver):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await manager._deliver_with_retry(webhook, "pr.merged", {})

        log = manager.get_delivery_log()
        assert log[-1]["status"] == "success"

    @pytest.mark.asyncio
    async def test_deliver_with_retry_fails_after_max_retries(self):
        """After MAX_RETRIES failures, logs a final 'failed' entry."""
        manager = WebhookManager()
        wid = manager.register_webhook("https://example.com", ["pr.merged"])
        webhook = manager._webhooks[wid]

        with patch.object(
            manager, "_deliver_once", new_callable=AsyncMock, side_effect=Exception("Error")
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await manager._deliver_with_retry(webhook, "pr.merged", {})

        log = manager.get_delivery_log()
        final = log[-1]
        assert final["status"] == "failed"
        assert final["attempt"] == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_deliver_with_retry_non_2xx_logs_failure(self):
        """A 4xx/5xx response eventually causes a failed delivery log."""
        manager = WebhookManager()
        wid = manager.register_webhook("https://example.com", ["pr.merged"])
        webhook = manager._webhooks[wid]

        with patch.object(manager, "_deliver_once", new_callable=AsyncMock, return_value=500):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await manager._deliver_with_retry(webhook, "pr.merged", {})

        log = manager.get_delivery_log()
        assert log[-1]["status"] == "failed"
        assert log[-1]["response_code"] == 500


class TestGetWebhookManagerSingleton:
    """Tests for the module-level singleton."""

    def test_get_webhook_manager_returns_instance(self):
        """get_webhook_manager() returns a WebhookManager instance."""
        manager = get_webhook_manager()
        assert isinstance(manager, WebhookManager)

    def test_get_webhook_manager_is_singleton(self):
        """get_webhook_manager() always returns the same object."""
        m1 = get_webhook_manager()
        m2 = get_webhook_manager()
        assert m1 is m2


# ---------------------------------------------------------------------------
# Integration Tests: Server REST API
# ---------------------------------------------------------------------------

class TestWebhookAPIEndpoints(AioHTTPTestCase):
    """Integration tests for the webhook REST API endpoints."""

    async def get_application(self):
        """Create test application."""
        self.temp_dir = tempfile.mkdtemp()

        # Reset the webhook manager singleton for a clean slate
        import dashboard.webhooks as wm_module
        wm_module._webhook_manager = None

        from dashboard.server import DashboardServer
        server = DashboardServer(
            project_name="test-webhook",
            metrics_dir=Path(self.temp_dir),
            port=0,
        )
        return server.app

    async def test_get_webhooks_empty(self):
        """GET /api/webhooks returns empty list when no webhooks registered."""
        resp = await self.client.get("/api/webhooks")
        assert resp.status == 200
        data = await resp.json()
        assert "webhooks" in data
        assert data["webhooks"] == []
        assert "valid_events" in data

    async def test_post_webhook_creates_webhook(self):
        """POST /api/webhooks creates a new webhook and returns 201."""
        payload = {
            "url": "https://ci.example.com/webhook",
            "events": ["pr.created", "pr.merged"],
            "secret": "test-secret",
        }
        resp = await self.client.post(
            "/api/webhooks",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 201
        data = await resp.json()
        assert data["url"] == payload["url"]
        assert data["events"] == payload["events"]
        assert "id" in data
        assert "secret" not in data

    async def test_post_webhook_missing_url_returns_400(self):
        """POST /api/webhooks without url returns 400."""
        payload = {"events": ["pr.merged"]}
        resp = await self.client.post(
            "/api/webhooks",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data

    async def test_post_webhook_missing_events_returns_400(self):
        """POST /api/webhooks without events returns 400."""
        payload = {"url": "https://example.com"}
        resp = await self.client.post(
            "/api/webhooks",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    async def test_post_webhook_invalid_events_returns_400(self):
        """POST /api/webhooks with invalid event type returns 400."""
        payload = {"url": "https://example.com", "events": ["not.valid"]}
        resp = await self.client.post(
            "/api/webhooks",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    async def test_delete_webhook(self):
        """DELETE /api/webhooks/{id} removes a registered webhook."""
        # Create webhook first
        payload = {
            "url": "https://delete-me.com/hook",
            "events": ["pr.merged"],
        }
        create_resp = await self.client.post(
            "/api/webhooks",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert create_resp.status == 201
        webhook_data = await create_resp.json()
        webhook_id = webhook_data["id"]

        # Delete it
        del_resp = await self.client.delete(f"/api/webhooks/{webhook_id}")
        assert del_resp.status == 204

        # Verify it's gone
        list_resp = await self.client.get("/api/webhooks")
        list_data = await list_resp.json()
        assert all(w["id"] != webhook_id for w in list_data["webhooks"])

    async def test_delete_nonexistent_webhook_returns_404(self):
        """DELETE /api/webhooks/{id} returns 404 for unknown ID."""
        resp = await self.client.delete("/api/webhooks/nonexistent-id")
        assert resp.status == 404

    async def test_get_deliveries_empty(self):
        """GET /api/webhooks/deliveries returns empty list initially."""
        resp = await self.client.get("/api/webhooks/deliveries")
        assert resp.status == 200
        data = await resp.json()
        assert "deliveries" in data
        assert isinstance(data["deliveries"], list)

    async def test_inbound_run_ticket(self):
        """POST /api/webhooks/inbound/run-ticket returns 202 Accepted."""
        payload = {"ticket_key": "AI-229", "agent": "coding"}
        resp = await self.client.post(
            "/api/webhooks/inbound/run-ticket",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 202
        data = await resp.json()
        assert data["accepted"] is True
        assert data["ticket_key"] == "AI-229"
        assert data["agent"] == "coding"

    async def test_inbound_run_ticket_missing_key_returns_400(self):
        """POST /api/webhooks/inbound/run-ticket without ticket_key returns 400."""
        payload = {"agent": "coding"}
        resp = await self.client.post(
            "/api/webhooks/inbound/run-ticket",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    async def test_inbound_run_spec(self):
        """POST /api/webhooks/inbound/run-spec returns 202 Accepted."""
        payload = {"spec": "Build a login form with OAuth", "agent": "coding"}
        resp = await self.client.post(
            "/api/webhooks/inbound/run-spec",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 202
        data = await resp.json()
        assert data["accepted"] is True
        assert data["spec_length"] > 0

    async def test_inbound_run_spec_missing_spec_returns_400(self):
        """POST /api/webhooks/inbound/run-spec without spec returns 400."""
        payload = {"agent": "coding"}
        resp = await self.client.post(
            "/api/webhooks/inbound/run-spec",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    async def test_test_webhook_not_found_returns_404(self):
        """POST /api/webhooks/{id}/test returns 404 for unknown webhook."""
        resp = await self.client.post("/api/webhooks/fake-id/test")
        assert resp.status == 404

    async def test_get_webhooks_lists_created_webhook(self):
        """GET /api/webhooks lists a webhook created via POST."""
        payload = {
            "url": "https://check-list.com/hook",
            "events": ["ticket.transitioned"],
        }
        await self.client.post(
            "/api/webhooks",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        list_resp = await self.client.get("/api/webhooks")
        data = await list_resp.json()
        urls = [w["url"] for w in data["webhooks"]]
        assert "https://check-list.com/hook" in urls
