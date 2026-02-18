"""Billing package for Agent Dashboard (AI-221).

Provides Stripe billing integration with:
- StripeClient: HTTP-based Stripe API wrapper using aiohttp
- StripeWebhookHandler: Webhook event processing
- SubscriptionStore: Subscription record persistence
- UsageTracker: Agent-hour usage tracking and Stripe reporting
"""
