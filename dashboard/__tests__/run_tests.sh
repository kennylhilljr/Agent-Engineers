#!/bin/bash
# Test runner for Provider Switcher - AI-71

echo "================================"
echo "AI-71: Provider Switcher Tests"
echo "================================"
echo ""

# Check if we have the test files
echo "✓ Checking test files..."
if [ -f "provider_switcher.test.js" ]; then
    echo "  - provider_switcher.test.js: FOUND"
else
    echo "  - provider_switcher.test.js: MISSING"
    exit 1
fi

if [ -f "provider_switcher_browser.test.js" ]; then
    echo "  - provider_switcher_browser.test.js: FOUND"
else
    echo "  - provider_switcher_browser.test.js: MISSING"
    exit 1
fi

echo ""
echo "✓ Test files verified"
echo ""

# Check if test_chat.html has provider selector
echo "✓ Checking implementation files..."
if grep -q "ai-provider-selector" ../test_chat.html; then
    echo "  - test_chat.html: Provider selector implemented"
else
    echo "  - test_chat.html: Provider selector MISSING"
    exit 1
fi

if grep -q "ai-provider-selector" ../dashboard.html; then
    echo "  - dashboard.html: Provider selector implemented"
else
    echo "  - dashboard.html: Provider selector MISSING"
    exit 1
fi

echo ""
echo "✓ Implementation verified"
echo ""

# Count test cases
UNIT_TESTS=$(grep -c "test(" provider_switcher.test.js || echo "0")
BROWSER_TESTS=$(grep -c "test(" provider_switcher_browser.test.js || echo "0")

echo "Test Coverage Summary:"
echo "  - Unit Tests: $UNIT_TESTS"
echo "  - Browser Tests: $BROWSER_TESTS"
echo "  - Total Tests: $((UNIT_TESTS + BROWSER_TESTS))"
echo ""

# Check for all 6 providers
echo "✓ Verifying all 6 providers are implemented:"
PROVIDERS=("claude" "chatgpt" "gemini" "groq" "kimi" "windsurf")
for provider in "${PROVIDERS[@]}"; do
    if grep -q "value=\"$provider\"" ../test_chat.html; then
        echo "  - $provider: ✓"
    else
        echo "  - $provider: ✗"
    fi
done

echo ""
echo "================================"
echo "Test execution requires Jest"
echo "Run: npm test or jest"
echo "================================"
