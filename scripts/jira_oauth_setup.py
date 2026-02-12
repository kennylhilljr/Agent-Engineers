#!/usr/bin/env python3
"""
Jira OAuth 2.0 (3LO) Setup
============================

One-time setup script to establish OAuth consent with Atlassian.
Run this once, then the system auto-refreshes tokens indefinitely.

Prerequisites:
  1. Create an OAuth 2.0 (3LO) app at https://developer.atlassian.com/console/myapps/
  2. Set callback URL to http://localhost:8914/callback
  3. Add scopes: read:jira-work, write:jira-work, read:jira-user, offline_access
  4. Add to .env:
       JIRA_OAUTH_CLIENT_ID=<your-client-id>
       JIRA_OAUTH_CLIENT_SECRET=<your-client-secret>

Usage:
    python scripts/jira_oauth_setup.py
"""

import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv()

try:
    from scripts.jira_auth import JiraAuthManager
except ImportError:
    from jira_auth import JiraAuthManager

# Atlassian OAuth endpoints
AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

CALLBACK_HOST = "localhost"
CALLBACK_PORT = 8914
CALLBACK_PATH = "/callback"
REDIRECT_URI = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}"

SCOPES = "read:jira-work write:jira-work read:jira-user offline_access"


def main():
    client_id = os.environ.get("JIRA_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("JIRA_OAUTH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("ERROR: JIRA_OAUTH_CLIENT_ID and JIRA_OAUTH_CLIENT_SECRET must be set in .env")
        print()
        print("To set up:")
        print("  1. Go to https://developer.atlassian.com/console/myapps/")
        print("  2. Create an OAuth 2.0 (3LO) app")
        print(f"  3. Set callback URL to {REDIRECT_URI}")
        print("  4. Add scopes: read:jira-work, write:jira-work, read:jira-user, offline_access")
        print("  5. Copy Client ID and Secret to .env")
        sys.exit(1)

    state = secrets.token_urlsafe(32)

    # Build authorization URL
    params = urllib.parse.urlencode({
        "audience": "api.atlassian.com",
        "client_id": client_id,
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    })
    auth_url = f"{AUTHORIZE_URL}?{params}"

    # Capture the authorization code via local HTTP server
    auth_code = [None]
    server_error = [None]

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != CALLBACK_PATH:
                self.send_response(404)
                self.end_headers()
                return

            qs = urllib.parse.parse_qs(parsed.query)
            received_state = qs.get("state", [None])[0]
            code = qs.get("code", [None])[0]
            error = qs.get("error", [None])[0]

            if error:
                server_error[0] = error
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h2>Authorization failed: {error}</h2>".encode())
                return

            if received_state != state:
                server_error[0] = "State mismatch"
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h2>Error: State mismatch</h2>")
                return

            auth_code[0] = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h2>Authorization successful!</h2>"
                b"<p>You can close this tab and return to the terminal.</p>"
            )

        def log_message(self, format, *args):
            pass  # Suppress server logs

    server = http.server.HTTPServer((CALLBACK_HOST, CALLBACK_PORT), CallbackHandler)

    print("Opening browser for Atlassian authorization...")
    print(f"If the browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for authorization callback...")
    # Handle one request then stop
    server.handle_request()
    server.server_close()

    if server_error[0]:
        print(f"ERROR: {server_error[0]}")
        sys.exit(1)

    if not auth_code[0]:
        print("ERROR: No authorization code received")
        sys.exit(1)

    print("Authorization code received. Exchanging for tokens...")

    # Exchange auth code for tokens
    body = json.dumps({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code[0],
        "redirect_uri": REDIRECT_URI,
    }).encode()

    req = urllib.request.Request(
        TOKEN_URL, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        token_data = json.loads(resp.read().decode())

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)

    if not refresh_token:
        print("WARNING: No refresh token returned. Make sure 'offline_access' scope is included.")

    print("Tokens received. Fetching accessible Jira sites...")

    # Get cloud ID
    req = urllib.request.Request(
        RESOURCES_URL, method="GET",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resources = json.loads(resp.read().decode())

    if not resources:
        print("ERROR: No accessible Jira sites found for this account.")
        sys.exit(1)

    if len(resources) == 1:
        cloud_id = resources[0]["id"]
        site_name = resources[0].get("name", resources[0].get("url", "unknown"))
        print(f"Found Jira site: {site_name}")
    else:
        print("Multiple Jira sites found:")
        for i, r in enumerate(resources):
            print(f"  [{i}] {r.get('name', r.get('url', 'unknown'))} (id: {r['id']})")
        choice = input("Select site number: ").strip()
        idx = int(choice)
        cloud_id = resources[idx]["id"]

    # Save tokens
    auth_manager = JiraAuthManager()
    auth_manager.save_initial_tokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        cloud_id=cloud_id,
    )

    print()
    print("Setup complete! OAuth tokens saved to .jira_tokens.json")
    print("The system will now auto-refresh tokens. No further action needed.")
    print()
    print("To verify, run:")
    print('  python -c "from scripts.jira_client import JiraClient; j = JiraClient(); print(j.health_check())"')


if __name__ == "__main__":
    main()
