# Security Audit Documentation

**AI Issue:** AI-199
**Audit Date:** 2026-02-18

## Overview

This document provides a security audit of the Agent Dashboard dependencies
and known security considerations.

## Dependency Security Status

Key dependencies and their known security status as of 2026-02-18:

| Package | Version | Status | Notes |
|---------|---------|--------|-------|
| `aiohttp` | >=3.9.0 | OK | Used for async HTTP server |
| `cryptography` | 46.0.4 | OK | Latest stable release |
| `PyJWT` | 2.10.1 | OK | Used for token validation |
| `pydantic` | 2.12.5 | OK | Latest stable release |
| `httpx` | 0.28.1 | OK | Used for HTTP client calls |
| `mcp` | 1.26.0 | OK | MCP protocol library |
| `starlette` | 0.52.1 | OK | ASGI framework |
| `uvicorn` | 0.40.0 | OK | ASGI server |
| `openai` | >=1.0.0 | OK | OpenAI SDK |

## Security Considerations

### Authentication

- Bearer token authentication is optional but recommended for production.
- Set `DASHBOARD_AUTH_TOKEN` environment variable to enable authentication.
- The `/api/health` endpoint is always unauthenticated.
- Auth tokens are compared using `hmac.compare_digest()` to prevent timing attacks.

### CORS

- Default CORS setting is `*` (allow all origins) — acceptable for development.
- For production, set `DASHBOARD_CORS_ORIGINS` to specific trusted origins.
- Example: `DASHBOARD_CORS_ORIGINS=https://app.example.com,https://admin.example.com`

### API Keys

- All API keys (Linear, Anthropic, OpenAI, etc.) are loaded from environment variables.
- API keys are never logged or exposed in API responses.
- Provider bridges degrade gracefully when API keys are absent.

### Host Binding

- Default host is `127.0.0.1` (loopback only) — safe for development.
- Setting `DASHBOARD_HOST=0.0.0.0` exposes the server on all interfaces.
- For production, use a reverse proxy (nginx, caddy) with TLS/SSL.

### Input Validation

- Chat messages are processed through the intent parser before routing.
- Ticket keys are validated against `[A-Z]+-\d+` regex pattern.
- Agent names are validated against the `KNOWN_AGENTS` set.

## Recommendations

1. Always set `DASHBOARD_AUTH_TOKEN` in production deployments.
2. Restrict `DASHBOARD_CORS_ORIGINS` to known origins in production.
3. Run behind a reverse proxy with TLS for any external exposure.
4. Rotate API keys regularly and use secrets management (e.g., HashiCorp Vault).
5. Monitor access logs for unusual patterns.
6. Run `pip-audit` or `safety check` regularly to detect known CVEs.

## Running a Dependency Security Scan

```bash
# Install pip-audit
pip install pip-audit

# Scan dependencies
pip-audit -r requirements.txt

# Or use safety
pip install safety
safety check -r requirements.txt
```

## Changelog

| Date | Action |
|------|--------|
| 2026-02-18 | Initial security audit document created (AI-199) |
