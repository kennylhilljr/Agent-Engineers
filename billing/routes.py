"""Billing API routes for Agent Dashboard (AI-247).

Registers aiohttp routes for:
    GET  /api/billing/tiers          List all available pricing tiers
    GET  /api/billing/current        Get current user's billing info
    POST /api/billing/upgrade        Upgrade/downgrade tier
    POST /api/billing/trial/start    Start a trial period
    GET  /api/pricing                Serve pricing page HTML
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from aiohttp import web

from .overage import calculate_overage, get_trial_status
from .pricing import (
    TIER_PRICE_CONFIGS,
    TRIAL_ELIGIBLE_TIERS,
    get_annual_savings_pct,
    get_stripe_price_id,
)
from .tiers import TIERS, TIER_ORDER, get_tier, is_upgrade, is_downgrade

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tier_to_dict(tier_id: str, billing_period: str = "monthly") -> Dict[str, Any]:
    """Serialise a TierDefinition to a JSON-friendly dict."""
    tier = get_tier(tier_id)
    config = TIER_PRICE_CONFIGS.get(tier_id)
    savings_pct = get_annual_savings_pct(tier_id)

    return {
        "tier_id": tier.tier_id,
        "name": tier.name,
        "monthly_price_usd": tier.monthly_price_usd,
        "annual_price_usd": tier.annual_price_usd,
        "agent_hours_per_month": tier.agent_hours_per_month,
        "concurrent_agents": tier.concurrent_agents,
        "allowed_models": tier.allowed_models,
        "features": tier.features,
        "overage_rate_per_hour": tier.overage_rate_per_hour,
        "premium_model_surcharge": tier.premium_model_surcharge,
        "trial_days": tier.trial_days,
        "is_custom_pricing": tier.is_custom_pricing,
        "min_monthly_price": tier.min_monthly_price,
        "stripe_price_id": get_stripe_price_id(tier_id, billing_period),
        "annual_savings_pct": savings_pct,
    }


def _json_response(data: Any, status: int = 200) -> web.Response:
    """Return an aiohttp JSON response."""
    return web.Response(
        text=json.dumps(data),
        content_type="application/json",
        status=status,
    )


def _error_response(message: str, status: int = 400) -> web.Response:
    """Return a standardised error JSON response."""
    return _json_response({"error": message}, status=status)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


async def list_tiers(request: web.Request) -> web.Response:
    """GET /api/billing/tiers — return all pricing tier definitions.

    Query parameters:
        billing_period: 'monthly' (default) or 'annual'
    """
    billing_period = request.rel_url.query.get("billing_period", "monthly")
    if billing_period not in ("monthly", "annual"):
        return _error_response("billing_period must be 'monthly' or 'annual'")

    tiers = [_tier_to_dict(tid, billing_period) for tid in TIER_ORDER]
    return _json_response({"tiers": tiers, "billing_period": billing_period})


async def get_current_billing(request: web.Request) -> web.Response:
    """GET /api/billing/current — return the current user's billing information.

    Expects the user's tier and usage to be available via request attributes
    (set by authentication middleware).  Falls back to 'explorer' tier if
    no auth context is present (for development/testing).
    """
    # Attempt to read user context from request (set by auth middleware)
    user_id: str = getattr(request, "user_id", "anonymous")
    tier_id: str = getattr(request, "user_tier", "explorer")
    used_hours: float = getattr(request, "used_hours", 0.0)
    premium_hours: float = getattr(request, "premium_hours", 0.0)
    trial_start: Optional[float] = getattr(request, "trial_start_ts", None)
    has_converted: bool = getattr(request, "trial_converted", False)

    overage = calculate_overage(tier_id, used_hours, premium_hours)
    trial = get_trial_status(tier_id, trial_start, has_converted)

    tier_info = _tier_to_dict(tier_id)

    return _json_response({
        "user_id": user_id,
        "tier": tier_info,
        "usage": {
            "used_hours": overage.used_hours,
            "included_hours": overage.included_hours,
            "overage_hours": overage.overage_hours,
            "overage_charge_usd": overage.overage_charge_usd,
            "premium_hours": overage.premium_hours,
            "premium_surcharge_usd": overage.premium_surcharge_usd,
            "total_charge_usd": overage.total_charge_usd,
            "is_hard_capped": overage.is_hard_capped,
        },
        "trial": {
            "is_on_trial": trial.is_on_trial,
            "days_remaining": trial.days_remaining,
            "trial_end": trial.trial_end,
            "has_converted": trial.has_converted,
            "is_expired": trial.is_expired,
        },
    })


async def upgrade_tier(request: web.Request) -> web.Response:
    """POST /api/billing/upgrade — upgrade or downgrade the user's tier.

    Request body (JSON):
        to_tier: Target tier identifier (required)
        billing_period: 'monthly' or 'annual' (default: 'monthly')

    Returns proration information and the Stripe Price ID to use for checkout.
    """
    try:
        body = await request.json()
    except Exception:
        return _error_response("Invalid JSON body")

    to_tier = body.get("to_tier", "").strip().lower()
    billing_period = body.get("billing_period", "monthly")

    if not to_tier:
        return _error_response("to_tier is required")

    if to_tier not in TIERS:
        return _error_response(f"Unknown tier '{to_tier}'")

    if billing_period not in ("monthly", "annual"):
        return _error_response("billing_period must be 'monthly' or 'annual'")

    current_tier: str = getattr(request, "user_tier", "explorer")

    if to_tier == current_tier:
        return _error_response("Already on this tier", status=409)

    target_tier = get_tier(to_tier)
    if target_tier.is_custom_pricing:
        return _json_response({
            "message": "Fleet tier requires a custom quote. Please contact sales.",
            "contact_url": "https://agent-dashboard.ai/contact-sales",
        })

    price_id = get_stripe_price_id(to_tier, billing_period)
    direction = "upgrade" if is_upgrade(current_tier, to_tier) else "downgrade"

    return _json_response({
        "from_tier": current_tier,
        "to_tier": to_tier,
        "billing_period": billing_period,
        "direction": direction,
        "stripe_price_id": price_id,
        "tier_info": _tier_to_dict(to_tier, billing_period),
        "message": (
            f"Redirecting to Stripe checkout for {target_tier.name} "
            f"({billing_period} billing)."
        ),
    })


async def start_trial(request: web.Request) -> web.Response:
    """POST /api/billing/trial/start — initiate a 14-day free trial.

    Request body (JSON):
        tier: Target tier for the trial (must be trial-eligible)

    Returns trial start/end timestamps.
    """
    try:
        body = await request.json()
    except Exception:
        return _error_response("Invalid JSON body")

    tier_id = body.get("tier", "").strip().lower()

    if not tier_id:
        return _error_response("tier is required")

    if tier_id not in TRIAL_ELIGIBLE_TIERS:
        eligible = ", ".join(sorted(TRIAL_ELIGIBLE_TIERS))
        return _error_response(
            f"Tier '{tier_id}' is not eligible for a trial. "
            f"Trial-eligible tiers: {eligible}"
        )

    now = time.time()
    trial_end = now + get_tier(tier_id).trial_days * 86400

    return _json_response({
        "tier": tier_id,
        "trial_start": now,
        "trial_end": trial_end,
        "trial_days": get_tier(tier_id).trial_days,
        "message": (
            f"Your {get_tier(tier_id).trial_days}-day free trial of "
            f"{get_tier(tier_id).name} has started."
        ),
    })


async def serve_pricing_page(request: web.Request) -> web.Response:
    """GET /api/pricing — serve the pricing HTML page."""
    pricing_html = Path(__file__).parent.parent / "dashboard" / "pricing.html"
    if pricing_html.exists():
        return web.Response(
            text=pricing_html.read_text(encoding="utf-8"),
            content_type="text/html",
        )
    return web.Response(
        text="<html><body><h1>Pricing page not found</h1></body></html>",
        content_type="text/html",
        status=404,
    )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_billing_routes(app: web.Application) -> None:
    """Register all billing routes on the aiohttp Application.

    Args:
        app: The aiohttp Application instance.
    """
    app.router.add_get("/api/billing/tiers", list_tiers)
    app.router.add_get("/api/billing/current", get_current_billing)
    app.router.add_post("/api/billing/upgrade", upgrade_tier)
    app.router.add_post("/api/billing/trial/start", start_trial)
    app.router.add_get("/api/pricing", serve_pricing_page)
    # Also serve pricing page at root /pricing path
    app.router.add_get("/pricing", serve_pricing_page)

    logger.info("Billing routes registered: /api/billing/tiers, /current, /upgrade, /trial/start, /api/pricing")
