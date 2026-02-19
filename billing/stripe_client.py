"""Stripe API client for Agent Dashboard (AI-221).

Lightweight HTTP client using aiohttp to call Stripe API endpoints.
Does NOT require the `stripe` Python package.

Environment variables:
    STRIPE_SECRET_KEY: Stripe secret key (sk_test_... or sk_live_...)
    STRIPE_PUBLISHABLE_KEY: Stripe publishable key (pk_test_... or pk_live_...)
    STRIPE_WEBHOOK_SECRET: Stripe webhook endpoint signing secret

If STRIPE_SECRET_KEY is not set, StripeNotConfiguredError is raised when
any API method is called.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stripe Price IDs per plan (replace with actual Stripe Price IDs in production)
# ---------------------------------------------------------------------------

STRIPE_PRICE_IDS: Dict[str, str] = {
    "explorer": "",  # free plan – no Stripe price ID
    "builder": os.environ.get("STRIPE_PRICE_BUILDER", "price_builder_mock"),
    "team": os.environ.get("STRIPE_PRICE_TEAM", "price_team_mock"),
    "organization": os.environ.get("STRIPE_PRICE_ORG", "price_org_mock"),
    "fleet": os.environ.get("STRIPE_PRICE_FLEET", "price_fleet_mock"),
}

STRIPE_API_BASE = "https://api.stripe.com/v1"


class StripeNotConfiguredError(Exception):
    """Raised when STRIPE_SECRET_KEY is not set in environment."""


class StripeAPIError(Exception):
    """Raised when the Stripe API returns an error response."""

    def __init__(self, message: str, status_code: int = 0, stripe_code: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.stripe_code = stripe_code


class StripeClient:
    """Lightweight Stripe API client using aiohttp.

    Uses the Stripe REST API directly (no stripe Python package required).
    All methods are async and should be awaited.

    Args:
        secret_key: Stripe secret key. Defaults to STRIPE_SECRET_KEY env var.

    Raises:
        StripeNotConfiguredError: if secret_key is empty/None.
    """

    def __init__(self, secret_key: Optional[str] = None) -> None:
        self._secret_key = secret_key or os.environ.get("STRIPE_SECRET_KEY", "")
        if not self._secret_key:
            raise StripeNotConfiguredError(
                "STRIPE_SECRET_KEY environment variable is not set. "
                "Stripe billing is disabled."
            )

    @property
    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated request to the Stripe API.

        Args:
            method: HTTP method (GET, POST, DELETE)
            path: API path (e.g. '/checkout/sessions')
            data: Form-encoded body data
            params: Query string parameters

        Returns:
            Parsed JSON response dict

        Raises:
            StripeAPIError: if the response indicates an error
        """
        try:
            import aiohttp
        except ImportError as exc:
            raise RuntimeError(
                "aiohttp is required for StripeClient. Install it with: pip install aiohttp"
            ) from exc

        url = f"{STRIPE_API_BASE}{path}"

        # Encode nested dicts as Stripe form params (e.g. metadata[key]=value)
        form_data: Optional[Dict[str, str]] = None
        if data:
            form_data = _flatten_stripe_params(data)

        async with aiohttp.ClientSession() as session:
            kwargs: Dict[str, Any] = {
                "headers": self._auth_headers,
            }
            if form_data:
                kwargs["data"] = form_data
            if params:
                kwargs["params"] = {k: str(v) for k, v in params.items()}

            async with session.request(method, url, **kwargs) as resp:
                body = await resp.json(content_type=None)

                if resp.status >= 400:
                    err = body.get("error", {})
                    raise StripeAPIError(
                        message=err.get("message", "Stripe API error"),
                        status_code=resp.status,
                        stripe_code=err.get("code", ""),
                    )

                return body

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    async def create_checkout_session(
        self,
        user_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        customer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe Checkout session.

        Args:
            user_id: Internal user ID (stored in metadata)
            price_id: Stripe Price ID for the subscription
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if user cancels checkout
            customer_id: Optional existing Stripe customer ID

        Returns:
            Checkout session dict (includes 'url' for redirect)
        """
        data: Dict[str, Any] = {
            "mode": "subscription",
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata[user_id]": user_id,
        }
        if customer_id:
            data["customer"] = customer_id
        else:
            data["client_reference_id"] = user_id

        logger.info(f"Creating Stripe Checkout session for user={user_id} price={price_id}")
        return await self._request("POST", "/checkout/sessions", data=data)

    # ------------------------------------------------------------------
    # Customer Portal
    # ------------------------------------------------------------------

    async def create_customer_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> Dict[str, Any]:
        """Create a Stripe Customer Portal session.

        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to after portal

        Returns:
            Portal session dict (includes 'url' for redirect)
        """
        data = {
            "customer": customer_id,
            "return_url": return_url,
        }
        logger.info(f"Creating Stripe Customer Portal session for customer={customer_id}")
        return await self._request("POST", "/billing_portal/sessions", data=data)

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Retrieve a subscription by ID.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Subscription dict
        """
        return await self._request("GET", f"/subscriptions/{subscription_id}")

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    async def list_invoices(
        self,
        customer_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """List invoices for a customer.

        Args:
            customer_id: Stripe customer ID
            limit: Maximum number of invoices to return (default 10)

        Returns:
            List of invoice dicts
        """
        params = {"customer": customer_id, "limit": str(limit)}
        result = await self._request("GET", "/invoices", params=params)
        return result.get("data", [])

    # ------------------------------------------------------------------
    # Usage Records
    # ------------------------------------------------------------------

    async def report_usage(
        self,
        subscription_item_id: str,
        quantity: int,
        timestamp: int,
        action: str = "set",
    ) -> Dict[str, Any]:
        """Report metered usage to Stripe.

        Args:
            subscription_item_id: Stripe subscription item ID
            quantity: Usage quantity to report
            timestamp: Unix timestamp for the usage record
            action: 'set' or 'increment' (default: 'set')

        Returns:
            Usage record dict
        """
        data = {
            "quantity": str(quantity),
            "timestamp": str(timestamp),
            "action": action,
        }
        logger.info(
            f"Reporting usage: subscription_item={subscription_item_id} "
            f"quantity={quantity} timestamp={timestamp}"
        )
        return await self._request(
            "POST",
            f"/subscription_items/{subscription_item_id}/usage_records",
            data=data,
        )

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    async def create_customer(
        self,
        email: str,
        user_id: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe customer.

        Args:
            email: Customer email
            user_id: Internal user ID (stored in metadata)
            name: Optional customer name

        Returns:
            Customer dict (includes 'id')
        """
        data: Dict[str, Any] = {
            "email": email,
            "metadata[user_id]": user_id,
        }
        if name:
            data["name"] = name
        return await self._request("POST", "/customers", data=data)

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Retrieve a customer by ID."""
        return await self._request("GET", f"/customers/{customer_id}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_stripe_params(
    data: Dict[str, Any],
    prefix: str = "",
) -> Dict[str, str]:
    """Flatten a nested dict into Stripe's form-encoded format.

    Example:
        {'metadata': {'user_id': '123'}} -> {'metadata[user_id]': '123'}

    For keys already in 'key[subkey]' format (pre-flattened), pass through as-is.
    """
    result: Dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}[{key}]" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_stripe_params(value, full_key))
        elif value is not None:
            result[full_key] = str(value)
    return result


# ---------------------------------------------------------------------------
# Mock data helpers (used when Stripe is not configured)
# ---------------------------------------------------------------------------

MOCK_INVOICES: List[Dict[str, Any]] = [
    {
        "id": "in_mock_001",
        "number": "INV-0001",
        "amount_paid": 4900,
        "currency": "usd",
        "status": "paid",
        "created": 1704067200,  # 2024-01-01
        "hosted_invoice_url": "#",
        "invoice_pdf": "#",
        "lines": {"data": [{"description": "Builder Plan - Monthly"}]},
    },
    {
        "id": "in_mock_002",
        "number": "INV-0002",
        "amount_paid": 4900,
        "currency": "usd",
        "status": "paid",
        "created": 1706745600,  # 2024-02-01
        "hosted_invoice_url": "#",
        "invoice_pdf": "#",
        "lines": {"data": [{"description": "Builder Plan - Monthly"}]},
    },
    {
        "id": "in_mock_003",
        "number": "INV-0003",
        "amount_paid": 4900,
        "currency": "usd",
        "status": "paid",
        "created": 1709251200,  # 2024-03-01
        "hosted_invoice_url": "#",
        "invoice_pdf": "#",
        "lines": {"data": [{"description": "Builder Plan - Monthly"}]},
    },
]

MOCK_SUBSCRIPTION: Dict[str, Any] = {
    "id": "sub_mock_001",
    "status": "active",
    "current_period_end": 9999999999,
    "items": {
        "data": [
            {
                "id": "si_mock_001",
                "price": {
                    "id": "price_builder_mock",
                    "unit_amount": 4900,
                    "currency": "usd",
                    "recurring": {"interval": "month"},
                },
            }
        ]
    },
}
