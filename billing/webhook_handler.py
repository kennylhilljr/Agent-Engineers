"""Stripe webhook handler for Agent Dashboard (AI-221).

Processes incoming Stripe webhook events, verifying HMAC-SHA256 signatures
and updating subscription state accordingly.

Supported events:
    checkout.session.completed
    customer.subscription.updated
    customer.subscription.deleted
    invoice.payment_succeeded
    invoice.payment_failed
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StripeWebhookHandler:
    """Processes Stripe webhook events.

    Args:
        subscription_store: SubscriptionStore instance for persistence.
        webhook_secret: Stripe webhook signing secret. Defaults to
            STRIPE_WEBHOOK_SECRET env var (resolved lazily).
    """

    def __init__(
        self,
        subscription_store: Any,  # SubscriptionStore, avoid circular import
        webhook_secret: Optional[str] = None,
    ) -> None:
        self._store = subscription_store
        self._webhook_secret = webhook_secret

    def _get_secret(self) -> str:
        """Return webhook secret from init arg or environment."""
        if self._webhook_secret:
            return self._webhook_secret
        import os
        secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        return secret

    def verify_signature(
        self,
        payload: bytes,
        sig_header: str,
        secret: Optional[str] = None,
    ) -> bool:
        """Verify Stripe webhook signature (HMAC-SHA256).

        Stripe sends a ``Stripe-Signature`` header with format:
            t=<timestamp>,v1=<signature>[,v1=<signature>...]

        The signed payload is: ``<timestamp>.<raw_body>``

        Args:
            payload: Raw request body bytes
            sig_header: Value of the ``Stripe-Signature`` HTTP header
            secret: Webhook signing secret (defaults to self._get_secret())

        Returns:
            True if the signature is valid, False otherwise.
        """
        if not sig_header:
            logger.warning("Webhook: missing Stripe-Signature header")
            return False

        signing_secret = secret or self._get_secret()
        if not signing_secret:
            logger.warning(
                "Webhook: STRIPE_WEBHOOK_SECRET not set - skipping signature verification"
            )
            # Allow through in dev mode (no secret configured)
            return True

        # Parse header: t=<ts>,v1=<sig>,...
        timestamp: Optional[str] = None
        signatures: list[str] = []

        for part in sig_header.split(","):
            part = part.strip()
            if part.startswith("t="):
                timestamp = part[2:]
            elif part.startswith("v1="):
                signatures.append(part[3:])

        if not timestamp or not signatures:
            logger.warning("Webhook: malformed Stripe-Signature header")
            return False

        # Protect against replay attacks (5 minute tolerance)
        try:
            event_ts = int(timestamp)
            now = int(time.time())
            if abs(now - event_ts) > 300:
                logger.warning(
                    f"Webhook: timestamp too old ({now - event_ts}s drift)"
                )
                return False
        except ValueError:
            logger.warning("Webhook: non-integer timestamp in Stripe-Signature")
            return False

        # Compute expected signature
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(
            signing_secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        # Compare against all provided v1 signatures
        for sig in signatures:
            if hmac.compare_digest(expected, sig):
                return True

        logger.warning("Webhook: signature mismatch")
        return False

    async def handle_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Dispatch a Stripe event to the appropriate handler.

        Args:
            event_type: Stripe event type string (e.g. 'checkout.session.completed')
            event_data: Stripe event 'data' dict (typically contains 'object')

        Returns:
            Result dict describing what was done.
        """
        obj = event_data.get("object", {})
        logger.info(f"Webhook: handling event type={event_type}")

        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_succeeded": self._handle_payment_succeeded,
            "invoice.payment_failed": self._handle_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler is None:
            logger.debug(f"Webhook: no handler for event_type={event_type}")
            return {"status": "ignored", "event_type": event_type}

        try:
            result = await handler(obj)
            result["event_type"] = event_type
            return result
        except Exception as exc:
            logger.exception(f"Webhook: error handling {event_type}: {exc}")
            return {"status": "error", "event_type": event_type, "error": str(exc)}

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _handle_checkout_completed(
        self, session: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle checkout.session.completed.

        When a user completes checkout, create or update their subscription record.
        """
        user_id = (
            session.get("metadata", {}).get("user_id")
            or session.get("client_reference_id")
        )
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")

        if not user_id:
            logger.warning("checkout.session.completed: no user_id in metadata")
            return {"status": "skipped", "reason": "no user_id"}

        # Determine plan from the line items metadata if available
        # For now, default to 'builder' when we can't determine
        plan = session.get("metadata", {}).get("plan", "builder")

        self._store.upsert_subscription(
            user_id=user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan=plan,
            status="active",
            current_period_end=None,
            grace_period_end=None,
        )
        logger.info(
            f"Webhook: checkout completed user={user_id} customer={customer_id} "
            f"subscription={subscription_id} plan={plan}"
        )
        return {"status": "ok", "action": "subscription_created", "user_id": user_id}

    async def _handle_subscription_updated(
        self, subscription: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle customer.subscription.updated."""
        subscription_id = subscription.get("id")
        customer_id = subscription.get("customer")
        status = subscription.get("status", "active")
        current_period_end = subscription.get("current_period_end")

        # Find user by customer_id
        record = self._store.get_subscription_by_customer(customer_id)
        if not record:
            logger.warning(
                f"subscription.updated: no record for customer={customer_id}"
            )
            return {"status": "skipped", "reason": "no matching record"}

        # Determine new plan from price metadata
        plan = _plan_from_subscription(subscription) or record.plan

        self._store.upsert_subscription(
            user_id=record.user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan=plan,
            status=status,
            current_period_end=current_period_end,
            grace_period_end=None,  # clear grace period on successful update
        )
        logger.info(
            f"Webhook: subscription updated user={record.user_id} "
            f"status={status} plan={plan}"
        )
        return {
            "status": "ok",
            "action": "subscription_updated",
            "user_id": record.user_id,
            "new_plan": plan,
            "new_status": status,
        }

    async def _handle_subscription_deleted(
        self, subscription: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle customer.subscription.deleted - downgrade to explorer plan."""
        customer_id = subscription.get("customer")

        record = self._store.get_subscription_by_customer(customer_id)
        if not record:
            logger.warning(
                f"subscription.deleted: no record for customer={customer_id}"
            )
            return {"status": "skipped", "reason": "no matching record"}

        self._store.upsert_subscription(
            user_id=record.user_id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=None,
            plan="explorer",
            status="canceled",
            current_period_end=subscription.get("current_period_end"),
            grace_period_end=None,
        )
        logger.info(
            f"Webhook: subscription deleted user={record.user_id} - downgraded to explorer"
        )
        return {
            "status": "ok",
            "action": "subscription_canceled",
            "user_id": record.user_id,
        }

    async def _handle_payment_succeeded(
        self, invoice: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle invoice.payment_succeeded - clear any grace period."""
        customer_id = invoice.get("customer")

        record = self._store.get_subscription_by_customer(customer_id)
        if not record:
            return {"status": "skipped", "reason": "no matching record"}

        # Clear grace period and mark as active
        if record.grace_period_end is not None:
            self._store.upsert_subscription(
                user_id=record.user_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=record.stripe_subscription_id,
                plan=record.plan,
                status="active",
                current_period_end=invoice.get("lines", {})
                    .get("data", [{}])[0]
                    .get("period", {})
                    .get("end"),
                grace_period_end=None,  # clear grace period
            )
            logger.info(
                f"Webhook: payment succeeded user={record.user_id} - grace period cleared"
            )
        return {"status": "ok", "action": "payment_succeeded", "user_id": record.user_id}

    async def _handle_payment_failed(
        self, invoice: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle invoice.payment_failed - set 3-day grace period."""
        customer_id = invoice.get("customer")

        record = self._store.get_subscription_by_customer(customer_id)
        if not record:
            return {"status": "skipped", "reason": "no matching record"}

        # Apply 3-day grace period
        self._store.set_grace_period(record.user_id, days=3)
        logger.info(
            f"Webhook: payment failed user={record.user_id} - 3-day grace period set"
        )
        return {
            "status": "ok",
            "action": "grace_period_set",
            "user_id": record.user_id,
            "grace_days": 3,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plan_from_subscription(subscription: Dict[str, Any]) -> Optional[str]:
    """Attempt to determine plan name from subscription price metadata."""
    from billing.stripe_client import STRIPE_PRICE_IDS

    items = subscription.get("items", {}).get("data", [])
    for item in items:
        price_id = item.get("price", {}).get("id", "")
        for plan, pid in STRIPE_PRICE_IDS.items():
            if pid and pid == price_id:
                return plan
    return None
