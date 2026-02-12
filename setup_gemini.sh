#!/bin/bash
# First-run setup script for Google Gemini CLI
# Guides user through installation and OAuth setup.

set -e

echo "=== Google Gemini CLI Setup ==="
echo ""

echo "[1/4] Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo "  ERROR: Node.js not found. Install from https://nodejs.org (v18+)"
    exit 1
fi
NODE_VERSION=$(node --version)
echo "  Found Node.js $NODE_VERSION"

echo ""
echo "[2/4] Installing @google/gemini-cli..."
if command -v gemini &> /dev/null; then
    GEMINI_VERSION=$(gemini --version 2>/dev/null || echo "unknown")
    echo "  Already installed: $GEMINI_VERSION"
else
    npm install -g @google/gemini-cli
    echo "  Installed successfully"
fi

echo ""
echo "[3/4] OAuth Authentication..."
echo "  This will open your browser for Google OAuth login."
echo "  Sign in with the Google account that has your AI Pro/Ultra subscription."
echo ""
read -p "  Press Enter to continue (or Ctrl+C to skip)..."
gemini -p "Hello, confirm you can hear me." --output-format json 2>/dev/null && echo "  Auth successful!" || echo "  Run 'gemini' manually to complete OAuth setup."

echo ""
echo "[4/4] Verification..."
echo "  Testing Gemini 2.5 Flash..."
RESPONSE=$(gemini -p "Say 'Gemini is ready' and nothing else." --model gemini-2.5-flash --output-format json 2>/dev/null || echo '{"error": "test failed"}')
echo "  Response: $RESPONSE"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Auth token stored at: ~/.gemini/ (persists across sessions)"
echo ""
echo "Add to your .env:"
echo "  GEMINI_AUTH_TYPE=cli-oauth"
echo "  GEMINI_MODEL=gemini-2.5-flash"
echo ""
echo "Test: python scripts/gemini_cli.py --status"
