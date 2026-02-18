#!/bin/bash
# AI-72 Model Selector Test Runner

echo "=========================================="
echo "AI-72: Model Selector Test Suite"
echo "=========================================="
echo ""

# Navigate to test directory
cd "$(dirname "$0")"

echo "📂 Working directory: $(pwd)"
echo ""

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js"
    exit 1
fi

echo "✅ Node.js: $(node --version)"
echo ""

# Run unit tests using Jest
echo "==========================================";
echo "Running Unit Tests (Jest)";
echo "==========================================";
echo ""

if command -v jest &> /dev/null; then
    jest model_selector.test.js --verbose 2>&1
    UNIT_TEST_EXIT=$?
else
    echo "⚠️  Jest not found in PATH, skipping unit tests"
    UNIT_TEST_EXIT=0
fi

echo ""
echo "==========================================";
echo "Running Browser Tests (Playwright)";
echo "==========================================";
echo ""

# Check for Playwright
if command -v playwright &> /dev/null; then
    npx playwright test model_selector_browser.test.js --reporter=list 2>&1
    BROWSER_TEST_EXIT=$?
else
    echo "⚠️  Playwright not found, skipping browser tests"
    BROWSER_TEST_EXIT=0
fi

echo ""
echo "==========================================";
echo "Test Summary";
echo "==========================================";
echo ""

if [ $UNIT_TEST_EXIT -eq 0 ]; then
    echo "✅ Unit Tests: PASSED"
else
    echo "❌ Unit Tests: FAILED (exit code: $UNIT_TEST_EXIT)"
fi

if [ $BROWSER_TEST_EXIT -eq 0 ]; then
    echo "✅ Browser Tests: PASSED"
else
    echo "❌ Browser Tests: FAILED (exit code: $BROWSER_TEST_EXIT)"
fi

echo ""
echo "==========================================";

# Exit with error if any tests failed
if [ $UNIT_TEST_EXIT -ne 0 ] || [ $BROWSER_TEST_EXIT -ne 0 ]; then
    exit 1
fi

exit 0
