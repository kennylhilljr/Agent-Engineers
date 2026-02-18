# Dashboard Environment Configuration (AI-111)

This document describes all environment variables supported by the Agent Dashboard server.

## Overview

All environment variables are **optional** with sensible defaults for development. Invalid values are handled gracefully with fallback to defaults and warning logs.

## Environment Variables

### DASHBOARD_WEB_PORT

Port for the web dashboard HTTP server.

- **Default:** `8420`
- **Valid Range:** 1-65535
- **Type:** Integer
- **Example:**
  ```bash
  export DASHBOARD_WEB_PORT=9000
  python -m dashboard.server
  ```

### DASHBOARD_WS_PORT

Port for WebSocket connections (real-time metrics streaming).

- **Default:** `8421`
- **Valid Range:** 1-65535
- **Type:** Integer
- **Note:** Must be different from `DASHBOARD_WEB_PORT`
- **Example:**
  ```bash
  export DASHBOARD_WS_PORT=9001
  python -m dashboard.server
  ```

### DASHBOARD_HOST

Host/interface to bind the dashboard server.

- **Default:** `0.0.0.0` (all interfaces)
- **Type:** String (hostname or IP address)
- **Common Values:**
  - `0.0.0.0` - All network interfaces (development)
  - `127.0.0.1` or `localhost` - localhost only (most secure)
  - `192.168.1.100` - Specific interface
- **Example:**
  ```bash
  export DASHBOARD_HOST=localhost
  python -m dashboard.server
  ```
- **Security Warning:**
  - `0.0.0.0` exposes the server to your network
  - For production, use a reverse proxy (nginx/caddy) with TLS/SSL
  - Consider setting to `127.0.0.1` for local development

### DASHBOARD_AUTH_TOKEN

Bearer token for API authentication (optional).

- **Default:** None (authentication disabled)
- **Type:** String
- **Usage:**
  When set, all endpoints (except `/api/health`) require authentication:
  ```bash
  curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8420/api/metrics
  ```
- **Example:**
  ```bash
  export DASHBOARD_AUTH_TOKEN=sk-dashboard-secret-123
  python -m dashboard.server
  ```
- **Security Notes:**
  - Use a strong, random token (32+ characters)
  - Store in secure environment variable management system
  - Rotate tokens regularly
  - Use HTTPS in production (via reverse proxy)

### DASHBOARD_CORS_ORIGINS

Allowed CORS origins for cross-origin requests.

- **Default:** `*` (allow all origins)
- **Type:** String
- **Format:** Comma-separated list of origins or wildcard `*`
- **Examples:**
  ```bash
  # Allow all origins (development only)
  export DASHBOARD_CORS_ORIGINS='*'

  # Allow specific domains
  export DASHBOARD_CORS_ORIGINS='https://dashboard.example.com,https://app.example.com'

  # Allow localhost only
  export DASHBOARD_CORS_ORIGINS='http://localhost:3000,http://localhost:8080'
  ```
- **Security Warning:**
  - `*` is acceptable for development but NOT for production
  - For production, set specific domains explicitly
  - Avoid using `*` with authentication enabled

## Usage Examples

### Development Configuration (localhost)

```bash
#!/bin/bash
export DASHBOARD_WEB_PORT=8420
export DASHBOARD_WS_PORT=8421
export DASHBOARD_HOST=localhost
export DASHBOARD_CORS_ORIGINS='http://localhost:3000,http://localhost:8080'
# No auth token - runs in open mode

python -m dashboard.server
```

### Production Configuration

```bash
#!/bin/bash
export DASHBOARD_WEB_PORT=8420
export DASHBOARD_WS_PORT=8421
export DASHBOARD_HOST=127.0.0.1
export DASHBOARD_AUTH_TOKEN=$(openssl rand -hex 32)  # Strong token
export DASHBOARD_CORS_ORIGINS='https://dashboard.example.com'

# Run behind nginx reverse proxy with SSL/TLS
python -m dashboard.server
```

### Docker Configuration

```dockerfile
FROM python:3.11

WORKDIR /app
COPY . .

ENV DASHBOARD_WEB_PORT=8420
ENV DASHBOARD_WS_PORT=8421
ENV DASHBOARD_HOST=0.0.0.0
ENV DASHBOARD_AUTH_TOKEN=your-secure-token
ENV DASHBOARD_CORS_ORIGINS=https://your-domain.com

RUN pip install -r requirements.txt

EXPOSE 8420 8421

CMD ["python", "-m", "dashboard.server"]
```

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  dashboard:
    build: .
    environment:
      DASHBOARD_WEB_PORT: 8420
      DASHBOARD_WS_PORT: 8421
      DASHBOARD_HOST: 0.0.0.0
      DASHBOARD_AUTH_TOKEN: ${DASHBOARD_AUTH_TOKEN}
      DASHBOARD_CORS_ORIGINS: https://dashboard.example.com
    ports:
      - "8420:8420"
      - "8421:8421"
    volumes:
      - ./.agent_metrics.json:/app/.agent_metrics.json
```

### Environment File (.env)

Create a `.env` file:

```bash
DASHBOARD_WEB_PORT=8420
DASHBOARD_WS_PORT=8421
DASHBOARD_HOST=localhost
DASHBOARD_AUTH_TOKEN=sk-example-token-123
DASHBOARD_CORS_ORIGINS=http://localhost:3000
```

Then load it:

```bash
set -a  # Export all variables
source .env
set +a  # Unset
python -m dashboard.server
```

## Validation and Error Handling

### Invalid Port

If `DASHBOARD_WEB_PORT` is invalid (not a number, out of range, etc.), it defaults to `8420` and logs a warning:

```python
import os
os.environ['DASHBOARD_WEB_PORT'] = 'invalid'

from dashboard.config import DashboardConfig
config = DashboardConfig()  # Logs warning, uses default 8420
assert config.web_port == 8420
```

### Port Conflict

If `DASHBOARD_WEB_PORT` and `DASHBOARD_WS_PORT` are the same, initialization fails:

```python
import os
os.environ['DASHBOARD_WEB_PORT'] = '8420'
os.environ['DASHBOARD_WS_PORT'] = '8420'

from dashboard.server import DashboardServer
# Raises ValueError: ports cannot be the same
server = DashboardServer(use_config=True)
```

### Invalid Host

Empty host strings default to `0.0.0.0` with a warning:

```python
import os
os.environ['DASHBOARD_HOST'] = ''

from dashboard.config import DashboardConfig
config = DashboardConfig()  # Logs warning, uses default 0.0.0.0
assert config.host == '0.0.0.0'
```

## Programmatic Usage

Access configuration in your code:

```python
from dashboard.config import get_config

config = get_config()

print(f"Web Port: {config.web_port}")      # 8420
print(f"WS Port: {config.ws_port}")        # 8421
print(f"Host: {config.host}")              # 0.0.0.0
print(f"Auth Enabled: {config.auth_enabled}")  # False or True
print(f"CORS Origins: {config.cors_origins}")  # * or comma-separated list

# Get CORS origins as list
origins_list = config.get_cors_origins_list()  # ['*'] or ['https://example.com', ...]

# Validate configuration
is_valid, error_msg = config.validate()
if not is_valid:
    print(f"Configuration error: {error_msg}")
```

## Server Integration

The dashboard server automatically loads and uses environment configuration:

```bash
# Command line - uses environment variables
DASHBOARD_WEB_PORT=9000 python -m dashboard.server

# Or with explicit overrides
python -m dashboard.server --port 9000 --host localhost
```

The `--port` and `--host` CLI arguments override environment variables:

```python
from dashboard.server import DashboardServer

# Loads from env, can be overridden
server = DashboardServer(
    use_config=True,
    port=9000,  # Overrides DASHBOARD_WEB_PORT
    host='127.0.0.1'  # Overrides DASHBOARD_HOST
)
```

## Logging

Configuration changes and security warnings are logged. Set `LOG_LEVEL` to see them:

```bash
export LOG_LEVEL=DEBUG
export DASHBOARD_HOST=0.0.0.0
python -m dashboard.server
```

Output:
```
DEBUG Dashboard Configuration (AI-111)
==============================================================
Web Port:      8420
WebSocket Port: 8421
Host:          0.0.0.0
Auth:          DISABLED
CORS Origins:  *
==============================================================
SECURITY WARNING: Host is 0.0.0.0 (all interfaces)...
SECURITY WARNING: CORS is set to allow all origins (*)...
```

## Migration from Older Versions

If you were previously using different configuration methods:

**Old way (deprecated):**
```bash
python dashboard/server.py --port 8000 --host localhost
```

**New way (recommended):**
```bash
export DASHBOARD_WEB_PORT=8000
export DASHBOARD_HOST=localhost
python -m dashboard.server
```

Both approaches still work. Environment variables provide better container/deployment support.

## Troubleshooting

### Port Already in Use

```
OSError: Address already in use
```

Solution: Change port or kill existing process:
```bash
# Change port
export DASHBOARD_WEB_PORT=9000

# Or find and kill existing process
lsof -i :8420
kill -9 <PID>
```

### Cannot Connect to Server

Check configuration:
```bash
# Default is 0.0.0.0 (all interfaces), should be accessible on localhost
curl http://localhost:8420/health

# If not working, check if host is 127.0.0.1 (localhost only)
python -c "from dashboard.config import get_config; print(get_config().host)"
```

### Authentication Required

If you get `401 Unauthorized`, set the auth token in request:
```bash
curl -H "Authorization: Bearer $DASHBOARD_AUTH_TOKEN" \
  http://localhost:8420/api/metrics
```

### CORS Issues

Check if frontend origin is in `DASHBOARD_CORS_ORIGINS`:
```bash
# View current setting
python -c "from dashboard.config import get_config; print(get_config().cors_origins)"

# Set for your frontend domain
export DASHBOARD_CORS_ORIGINS='https://myapp.example.com'
```

## Related Documentation

- [Dashboard Server Documentation](./DASHBOARD_SERVER.md)
- [API Endpoints](./API_ENDPOINTS.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Security Best Practices](./SECURITY.md)
