"""Tests for billing module (AI-221).

Covers:
- StripeClient configuration and error handling
- StripeWebhookHandler signature verification and event handling
- SubscriptionStore CRUD operations and grace period logic
- UsageTracker recording and aggregation
- REST API endpoints (mocked Stripe)

Aims for 30+ tests.
"""

import asyncio
import hashlib
import hmac
import json
import os
import time
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

# Ensure billing module is importable from project root
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from billing.stripe_client import (
    StripeClient,
    StripeNotConfiguredError,
    StripeAPIError,
    STRIPE_PRICE_IDS,
    MOCK_INVOICES,
    MOCK_SUBSCRIPTION,
    _flatten_stripe_params,
)
from billing.subscription_store import (
    SubscriptionRecord,
    SubscriptionStore,
    get_subscription_store,
    reset_subscription_store,
)
from billing.usage_tracker import (
    UsageEntry,
    UsageTracker,
    get_usage_tracker,
    reset_usage_tracker,
)
from billing.webhook_handler import StripeWebhookHandler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir(tmp_path):
    """Return a temporary directory Path."""
    return tmp_path


@pytest.fixture
def subscription_store(tmp_dir):
    """Return a SubscriptionStore backed by a temp file."""
    return SubscriptionStore(data_file=tmp_dir / "subscriptions.json")


@pytest.fixture
def usage_tracker(tmp_dir):
    """Return a UsageTracker backed by a temp file."""
    return UsageTracker(log_file=tmp_dir / "usage_log.json")


@pytest.fixture
def webhook_handler(subscription_store):
    """Return a StripeWebhookHandler with a test secret."""
    return StripeWebhookHandler(
        subscription_store=subscription_store,
        webhook_secret="whsec_test_secret",
    )


# ---------------------------------------------------------------------------
# StripeClient tests (1-10)
# ---------------------------------------------------------------------------


class TestStripeClientConfiguration:
    """Tests for StripeClient configuration and error handling."""

    def test_raises_if_no_key(self):
        """StripeNotConfiguredError raised when no secret key."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove STRIPE_SECRET_KEY if present
            env = {k: v for k, v in os.environ.items() if k != "STRIPE_SECRET_KEY"}
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(StripeNotConfiguredError):
                    StripeClient(secret_key="")

    def test_raises_with_empty_string(self):
        """StripeNotConfiguredError raised with empty string key."""
        with pytest.raises(StripeNotConfiguredError):
            StripeClient(secret_key="")

    def test_succeeds_with_key(self):
        """StripeClient created successfully when key provided."""
        client = StripeClient(secret_key="sk_test_fake_key")
        assert client is not None

    def test_reads_key_from_env(self):
        """StripeClient reads key from STRIPE_SECRET_KEY environment variable."""
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_env_key"}):
            client = StripeClient()
            assert client._secret_key == "sk_test_env_key"

    def test_auth_headers_include_bearer(self):
        """Auth headers include 'Bearer <key>'."""
        client = StripeClient(secret_key="sk_test_abc")
        headers = client._auth_headers
        assert headers["Authorization"] == "Bearer sk_test_abc"

    def test_stripe_price_ids_has_plans(self):
        """STRIPE_PRICE_IDS contains all expected plans."""
        assert "explorer" in STRIPE_PRICE_IDS
        assert "builder" in STRIPE_PRICE_IDS
        assert "team" in STRIPE_PRICE_IDS
        assert "organization" in STRIPE_PRICE_IDS

    def test_explorer_plan_has_no_price(self):
        """Explorer plan has no Stripe price ID (free tier)."""
        assert STRIPE_PRICE_IDS["explorer"] == ""

    def test_flatten_stripe_params_simple(self):
        """_flatten_stripe_params flattens a simple dict."""
        result = _flatten_stripe_params({"key": "value"})
        assert result == {"key": "value"}

    def test_flatten_stripe_params_nested(self):
        """_flatten_stripe_params flattens nested dicts."""
        result = _flatten_stripe_params({"metadata": {"user_id": "u1"}})
        assert result == {"metadata[user_id]": "u1"}

    def test_flatten_stripe_params_deep(self):
        """_flatten_stripe_params handles deeper nesting."""
        result = _flatten_stripe_params({"a": {"b": {"c": "d"}}})
        assert result == {"a[b][c]": "d"}

    def test_mock_invoices_structure(self):
        """MOCK_INVOICES has expected structure."""
        assert len(MOCK_INVOICES) > 0
        inv = MOCK_INVOICES[0]
        assert "id" in inv
        assert "amount_paid" in inv
        assert "status" in inv
        assert "created" in inv

    @pytest.mark.asyncio
    async def test_create_checkout_session_mock(self):
        """create_checkout_session calls correct Stripe endpoint."""
        client = StripeClient(secret_key="sk_test_key")

        mock_response = {
            "id": "cs_test_abc",
            "url": "https://checkout.stripe.com/test",
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            result = await client.create_checkout_session(
                user_id="u1",
                price_id="price_builder",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )
            assert result["url"] == "https://checkout.stripe.com/test"
            mock_req.assert_called_once()
            call_args = mock_req.call_args
            assert call_args[0][0] == "POST"
            assert "/checkout/sessions" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_list_invoices_returns_data(self):
        """list_invoices returns invoice list from response."""
        client = StripeClient(secret_key="sk_test_key")
        mock_response = {"data": MOCK_INVOICES, "has_more": False}

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            result = await client.list_invoices("cus_test", limit=5)
            assert result == MOCK_INVOICES

    @pytest.mark.asyncio
    async def test_get_subscription_calls_correct_path(self):
        """get_subscription calls GET /subscriptions/{id}."""
        client = StripeClient(secret_key="sk_test_key")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = MOCK_SUBSCRIPTION
            result = await client.get_subscription("sub_test_123")
            mock_req.assert_called_once_with("GET", "/subscriptions/sub_test_123")


# ---------------------------------------------------------------------------
# StripeWebhookHandler tests (11-20)
# ---------------------------------------------------------------------------


class TestStripeWebhookHandlerSignature:
    """Tests for webhook signature verification."""

    def _make_sig_header(self, payload: bytes, secret: str, ts: Optional[int] = None) -> str:
        """Generate a valid Stripe-Signature header for testing."""
        if ts is None:
            ts = int(time.time())
        signed_payload = f"{ts}.".encode() + payload
        sig = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        return f"t={ts},v1={sig}"

    def test_valid_signature_returns_true(self, webhook_handler):
        """Valid signature returns True."""
        payload = b'{"type":"test"}'
        sig = self._make_sig_header(payload, "whsec_test_secret")
        assert webhook_handler.verify_signature(payload, sig) is True

    def test_invalid_signature_returns_false(self, webhook_handler):
        """Wrong signature returns False."""
        payload = b'{"type":"test"}'
        sig = self._make_sig_header(payload, "wrong_secret")
        assert webhook_handler.verify_signature(payload, sig) is False

    def test_empty_sig_header_returns_false(self, webhook_handler):
        """Empty signature header returns False."""
        payload = b'{"type":"test"}'
        assert webhook_handler.verify_signature(payload, "") is False

    def test_missing_timestamp_returns_false(self, webhook_handler):
        """Malformed header without timestamp returns False."""
        payload = b'{"type":"test"}'
        assert webhook_handler.verify_signature(payload, "v1=abc123") is False

    def test_old_timestamp_returns_false(self, webhook_handler):
        """Old timestamp (>5 min) returns False."""
        payload = b'{"type":"test"}'
        old_ts = int(time.time()) - 400  # 400 seconds ago
        sig = self._make_sig_header(payload, "whsec_test_secret", ts=old_ts)
        assert webhook_handler.verify_signature(payload, sig) is False

    def test_no_secret_configured_allows_through(self, subscription_store):
        """When no webhook secret is set, signature check is skipped (dev mode)."""
        handler = StripeWebhookHandler(
            subscription_store=subscription_store,
            webhook_secret=None,
        )
        with patch.dict(os.environ, {}, clear=True):
            env = {k: v for k, v in os.environ.items() if k != "STRIPE_WEBHOOK_SECRET"}
            with patch.dict(os.environ, env, clear=True):
                result = handler.verify_signature(b"payload", "t=123,v1=xyz")
                assert result is True

    @pytest.mark.asyncio
    async def test_handle_unknown_event_returns_ignored(self, webhook_handler):
        """Unknown event types return status='ignored'."""
        result = await webhook_handler.handle_event("some.unknown.event", {"object": {}})
        assert result["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_checkout_completed_creates_subscription(self, webhook_handler, subscription_store):
        """checkout.session.completed creates a subscription record."""
        event_data = {
            "object": {
                "id": "cs_test_123",
                "customer": "cus_test_123",
                "subscription": "sub_test_123",
                "client_reference_id": "user_001",
                "metadata": {"user_id": "user_001", "plan": "builder"},
            }
        }
        result = await webhook_handler.handle_event(
            "checkout.session.completed", event_data
        )
        assert result["status"] == "ok"
        rec = subscription_store.get_subscription("user_001")
        assert rec is not None
        assert rec.stripe_customer_id == "cus_test_123"
        assert rec.plan == "builder"

    @pytest.mark.asyncio
    async def test_payment_failed_sets_grace_period(self, webhook_handler, subscription_store):
        """invoice.payment_failed sets a 3-day grace period."""
        # First create a subscription
        subscription_store.upsert_subscription(
            user_id="user_grace",
            stripe_customer_id="cus_grace",
            stripe_subscription_id="sub_grace",
            plan="team",
            status="active",
        )

        event_data = {"object": {"customer": "cus_grace"}}
        result = await webhook_handler.handle_event("invoice.payment_failed", event_data)

        assert result["status"] == "ok"
        assert result["action"] == "grace_period_set"
        assert result["grace_days"] == 3

        rec = subscription_store.get_subscription("user_grace")
        assert rec is not None
        assert rec.grace_period_end is not None
        assert rec.status == "past_due"

    @pytest.mark.asyncio
    async def test_subscription_deleted_downgrades_to_explorer(
        self, webhook_handler, subscription_store
    ):
        """customer.subscription.deleted downgrades user to explorer."""
        subscription_store.upsert_subscription(
            user_id="user_del",
            stripe_customer_id="cus_del",
            stripe_subscription_id="sub_del",
            plan="builder",
            status="active",
        )

        event_data = {"object": {"customer": "cus_del", "current_period_end": 9999999}}
        result = await webhook_handler.handle_event(
            "customer.subscription.deleted", event_data
        )
        assert result["status"] == "ok"
        rec = subscription_store.get_subscription("user_del")
        assert rec.plan == "explorer"
        assert rec.status == "canceled"

    @pytest.mark.asyncio
    async def test_payment_succeeded_clears_grace_period(
        self, webhook_handler, subscription_store
    ):
        """invoice.payment_succeeded clears grace period."""
        # Create subscription in past_due / grace period state
        subscription_store.upsert_subscription(
            user_id="user_recover",
            stripe_customer_id="cus_recover",
            stripe_subscription_id="sub_recover",
            plan="team",
            status="past_due",
            grace_period_end=int(time.time()) + 86400,
        )

        event_data = {"object": {"customer": "cus_recover"}}
        result = await webhook_handler.handle_event("invoice.payment_succeeded", event_data)

        assert result["status"] == "ok"
        rec = subscription_store.get_subscription("user_recover")
        assert rec.grace_period_end is None


# ---------------------------------------------------------------------------
# SubscriptionStore tests (21-28)
# ---------------------------------------------------------------------------


class TestSubscriptionStore:
    """Tests for SubscriptionStore CRUD and grace period logic."""

    def test_get_nonexistent_returns_none(self, subscription_store):
        """get_subscription returns None for unknown user."""
        assert subscription_store.get_subscription("nonexistent") is None

    def test_upsert_creates_record(self, subscription_store):
        """upsert_subscription creates a new record."""
        rec = subscription_store.upsert_subscription(
            user_id="u1",
            stripe_customer_id="cus_1",
            stripe_subscription_id="sub_1",
            plan="builder",
            status="active",
        )
        assert rec.user_id == "u1"
        assert rec.plan == "builder"
        assert rec.status == "active"

    def test_upsert_updates_existing_record(self, subscription_store):
        """upsert_subscription updates an existing record."""
        subscription_store.upsert_subscription(
            user_id="u2", plan="builder", status="active"
        )
        updated = subscription_store.upsert_subscription(
            user_id="u2", plan="team", status="trialing"
        )
        assert updated.plan == "team"
        assert updated.status == "trialing"

    def test_get_subscription_by_customer(self, subscription_store):
        """get_subscription_by_customer returns correct record."""
        subscription_store.upsert_subscription(
            user_id="u3",
            stripe_customer_id="cus_xyz",
            plan="team",
            status="active",
        )
        rec = subscription_store.get_subscription_by_customer("cus_xyz")
        assert rec is not None
        assert rec.user_id == "u3"

    def test_get_subscription_by_customer_none(self, subscription_store):
        """get_subscription_by_customer returns None if not found."""
        assert subscription_store.get_subscription_by_customer("cus_nobody") is None

    def test_set_grace_period(self, subscription_store):
        """set_grace_period sets grace_period_end and status to past_due."""
        subscription_store.upsert_subscription(
            user_id="u4",
            stripe_customer_id="cus_u4",
            plan="builder",
            status="active",
        )
        rec = subscription_store.set_grace_period("u4", days=3)
        assert rec is not None
        assert rec.status == "past_due"
        assert rec.grace_period_end is not None
        # Should be approximately 3 days from now
        expected_end = int(time.time()) + 3 * 86400
        assert abs(rec.grace_period_end - expected_end) < 5

    def test_is_in_grace_period_true(self, subscription_store):
        """is_in_grace_period returns True when in grace."""
        subscription_store.upsert_subscription(
            user_id="u5",
            stripe_customer_id="cus_u5",
            plan="builder",
            status="past_due",
            grace_period_end=int(time.time()) + 86400,
        )
        assert subscription_store.is_in_grace_period("u5") is True

    def test_is_in_grace_period_false_expired(self, subscription_store):
        """is_in_grace_period returns False when grace period has expired."""
        subscription_store.upsert_subscription(
            user_id="u6",
            stripe_customer_id="cus_u6",
            plan="builder",
            status="past_due",
            grace_period_end=int(time.time()) - 1,  # expired
        )
        assert subscription_store.is_in_grace_period("u6") is False

    def test_is_in_grace_period_false_no_record(self, subscription_store):
        """is_in_grace_period returns False for unknown user."""
        assert subscription_store.is_in_grace_period("nobody") is False

    def test_persistence_round_trip(self, tmp_dir):
        """SubscriptionStore persists and reloads records correctly."""
        data_file = tmp_dir / "subs_test.json"
        store1 = SubscriptionStore(data_file=data_file)
        store1.upsert_subscription(
            user_id="persist_user",
            stripe_customer_id="cus_persist",
            plan="organization",
            status="active",
        )

        # Load fresh store from same file
        store2 = SubscriptionStore(data_file=data_file)
        rec = store2.get_subscription("persist_user")
        assert rec is not None
        assert rec.plan == "organization"
        assert rec.stripe_customer_id == "cus_persist"

    def test_subscription_record_is_active_explorer(self, subscription_store):
        """Explorer plan is always considered active."""
        rec = SubscriptionRecord(user_id="u", plan="explorer", status="free")
        assert rec.is_active() is True

    def test_subscription_record_is_active_paid(self, subscription_store):
        """Active paid subscription is active."""
        rec = SubscriptionRecord(user_id="u", plan="builder", status="active")
        assert rec.is_active() is True

    def test_subscription_record_is_active_grace(self):
        """Past due within grace period is still active."""
        rec = SubscriptionRecord(
            user_id="u",
            plan="builder",
            status="past_due",
            grace_period_end=int(time.time()) + 86400,
        )
        assert rec.is_active() is True

    def test_subscription_record_not_active_canceled(self):
        """Canceled subscription is not active."""
        rec = SubscriptionRecord(user_id="u", plan="builder", status="canceled")
        assert rec.is_active() is False

    def test_list_all(self, subscription_store):
        """list_all returns all records."""
        subscription_store.upsert_subscription(user_id="ua", plan="builder", status="active")
        subscription_store.upsert_subscription(user_id="ub", plan="team", status="active")
        all_recs = subscription_store.list_all()
        user_ids = [r.user_id for r in all_recs]
        assert "ua" in user_ids
        assert "ub" in user_ids


# ---------------------------------------------------------------------------
# UsageTracker tests (29-38)
# ---------------------------------------------------------------------------


class TestUsageTracker:
    """Tests for UsageTracker recording and aggregation."""

    def test_record_session(self, usage_tracker):
        """record_agent_session creates a UsageEntry."""
        entry = usage_tracker.record_agent_session("u1", "sess1", 2.5)
        assert entry.user_id == "u1"
        assert entry.session_id == "sess1"
        assert entry.hours == 2.5
        assert entry.reported_to_stripe is False

    def test_record_session_negative_hours_raises(self, usage_tracker):
        """Negative hours raises ValueError."""
        with pytest.raises(ValueError):
            usage_tracker.record_agent_session("u1", "sess_bad", -1.0)

    def test_get_daily_usage(self, usage_tracker):
        """get_daily_usage returns correct total for a date."""
        today = date.today()
        usage_tracker.record_agent_session("u2", "s1", 1.0, timestamp=time.time())
        usage_tracker.record_agent_session("u2", "s2", 2.0, timestamp=time.time())
        total = usage_tracker.get_daily_usage("u2", today)
        assert abs(total - 3.0) < 0.01

    def test_get_daily_usage_different_user(self, usage_tracker):
        """get_daily_usage doesn't include other users."""
        usage_tracker.record_agent_session("u3", "s1", 5.0)
        usage_tracker.record_agent_session("u4", "s2", 3.0)
        total = usage_tracker.get_daily_usage("u3", date.today())
        assert abs(total - 5.0) < 0.01

    def test_get_monthly_usage(self, usage_tracker):
        """get_monthly_usage aggregates correctly."""
        now = datetime.now(timezone.utc)
        ts = now.timestamp()
        usage_tracker.record_agent_session("u5", "s1", 3.0, timestamp=ts)
        usage_tracker.record_agent_session("u5", "s2", 4.0, timestamp=ts)
        total = usage_tracker.get_monthly_usage("u5", now.year, now.month)
        assert abs(total - 7.0) < 0.01

    def test_get_monthly_usage_no_entries(self, usage_tracker):
        """get_monthly_usage returns 0 when no entries."""
        total = usage_tracker.get_monthly_usage("nobody", 2024, 1)
        assert total == 0.0

    def test_get_pending_stripe_entries(self, usage_tracker):
        """get_pending_stripe_entries returns unreported entries."""
        usage_tracker.record_agent_session("u6", "s1", 1.0)
        usage_tracker.record_agent_session("u6", "s2", 2.0)
        pending = usage_tracker.get_pending_stripe_entries()
        assert len(pending) >= 2
        assert all(not e.reported_to_stripe for e in pending)

    def test_get_pending_stripe_entries_by_user(self, usage_tracker):
        """get_pending_stripe_entries filters by user."""
        usage_tracker.record_agent_session("u7", "s1", 1.0)
        usage_tracker.record_agent_session("u8", "s2", 2.0)
        pending = usage_tracker.get_pending_stripe_entries(user_id="u7")
        assert all(e.user_id == "u7" for e in pending)

    def test_get_user_entries(self, usage_tracker):
        """get_user_entries returns entries for the given user."""
        usage_tracker.record_agent_session("u9", "s1", 0.5)
        usage_tracker.record_agent_session("u9", "s2", 1.0)
        entries = usage_tracker.get_user_entries("u9")
        assert len(entries) == 2

    def test_usage_persistence(self, tmp_dir):
        """UsageTracker persists and reloads entries."""
        log_file = tmp_dir / "usage_persist.json"
        tracker1 = UsageTracker(log_file=log_file)
        tracker1.record_agent_session("persist_u", "s1", 3.5)

        tracker2 = UsageTracker(log_file=log_file)
        entries = tracker2.get_user_entries("persist_u")
        assert len(entries) == 1
        assert entries[0].hours == 3.5

    @pytest.mark.asyncio
    async def test_flush_to_stripe_skips_explorer(self, usage_tracker, subscription_store):
        """flush_to_stripe skips explorer users (no Stripe subscription)."""
        usage_tracker.record_agent_session("explorer_u", "s1", 5.0)
        # Explorer user has no subscription record
        result = await usage_tracker.flush_to_stripe(None, subscription_store)
        assert result["skipped"] >= 1

    @pytest.mark.asyncio
    async def test_flush_to_stripe_marks_reported(self, usage_tracker, subscription_store):
        """flush_to_stripe marks entries as reported for subscribed users."""
        subscription_store.upsert_subscription(
            user_id="paid_u",
            stripe_customer_id="cus_paid",
            stripe_subscription_id="sub_paid",
            plan="builder",
            status="active",
        )
        usage_tracker.record_agent_session("paid_u", "s1", 2.0)
        result = await usage_tracker.flush_to_stripe(None, subscription_store)
        assert result["reported"] >= 1

        # Entries should now be marked as reported
        pending = usage_tracker.get_pending_stripe_entries(user_id="paid_u")
        assert len(pending) == 0


# ---------------------------------------------------------------------------
# REST API endpoint tests (39+)
# ---------------------------------------------------------------------------


@pytest.fixture
async def billing_api_client(tmp_dir):
    """Create an aiohttp TestClient wrapping the REST server."""
    from aiohttp.test_utils import TestClient, TestServer
    from dashboard.rest_api_server import RESTAPIServer

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_dir, port=0)
    client = TestClient(TestServer(server.app))
    await client.start_server()
    yield client
    await client.close()


class TestBillingAPIEndpoints:
    """Tests for REST API billing endpoints."""

    @pytest.mark.asyncio
    async def test_get_subscription_returns_explorer_default(self, billing_api_client):
        """GET /api/billing/subscription returns explorer data for new user."""
        reset_subscription_store()
        resp = await billing_api_client.get("/api/billing/subscription")
        assert resp.status == 200
        data = await resp.json()
        assert "plan" in data
        assert data["plan"] == "explorer"

    @pytest.mark.asyncio
    async def test_get_billing_checkout_no_stripe(self, billing_api_client):
        """GET /api/billing/checkout returns mock URL when Stripe not configured."""
        env = {k: v for k, v in os.environ.items() if k != "STRIPE_SECRET_KEY"}
        with patch.dict(os.environ, env, clear=True):
            resp = await billing_api_client.get("/api/billing/checkout?plan=builder")
            assert resp.status == 200
            data = await resp.json()
            assert data.get("mock") is True
            assert "url" in data

    @pytest.mark.asyncio
    async def test_get_billing_portal_no_stripe(self, billing_api_client):
        """GET /api/billing/portal returns mock URL when Stripe not configured."""
        env = {k: v for k, v in os.environ.items() if k != "STRIPE_SECRET_KEY"}
        with patch.dict(os.environ, env, clear=True):
            resp = await billing_api_client.get("/api/billing/portal")
            assert resp.status == 200
            data = await resp.json()
            assert data.get("mock") is True

    @pytest.mark.asyncio
    async def test_get_billing_invoices_returns_mock_data(self, billing_api_client):
        """GET /api/billing/invoices returns mock invoices when Stripe not configured."""
        env = {k: v for k, v in os.environ.items() if k != "STRIPE_SECRET_KEY"}
        with patch.dict(os.environ, env, clear=True):
            resp = await billing_api_client.get("/api/billing/invoices")
            assert resp.status == 200
            data = await resp.json()
            assert "invoices" in data
            assert data.get("mock") is True
            assert len(data["invoices"]) > 0

    @pytest.mark.asyncio
    async def test_stripe_webhook_no_secret_accepts_all(self, billing_api_client):
        """POST /api/billing/stripe-webhook accepts events when no secret configured."""
        env = {k: v for k, v in os.environ.items() if k != "STRIPE_WEBHOOK_SECRET"}
        with patch.dict(os.environ, env, clear=True):
            payload = json.dumps({
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test",
                        "customer": "cus_test",
                        "subscription": "sub_test",
                        "client_reference_id": "user_webhook_test",
                        "metadata": {"user_id": "user_webhook_test", "plan": "builder"},
                    }
                }
            })
            resp = await billing_api_client.post(
                "/api/billing/stripe-webhook",
                data=payload.encode(),
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=1,v1=invalid",
                },
            )
            # In dev mode (no secret), should be 200
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_stripe_webhook_invalid_signature_with_secret(self, billing_api_client):
        """POST /api/billing/stripe-webhook rejects bad signature when secret is set."""
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_real_secret"}):
            payload = b'{"type":"test","data":{"object":{}}}'
            resp = await billing_api_client.post(
                "/api/billing/stripe-webhook",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=1,v1=badsig",
                },
            )
            assert resp.status == 400
