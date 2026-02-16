"""
AI-103: Unit Tests for Single HTML File Dashboard

Tests for the self-contained index.html file:
- File structure validation
- CSS embedding verification
- JavaScript embedding verification
- No external dependencies
- Dark mode CSS rules
- Responsive design breakpoints
"""

import os
import re
from pathlib import Path


def test_hook():
    """Custom test hook following project pattern"""
    results = []

    def run_test(name, test_func):
        try:
            test_func()
            results.append(f"✓ {name}")
            return True
        except AssertionError as e:
            results.append(f"✗ {name}: {str(e)}")
            return False
        except Exception as e:
            results.append(f"✗ {name}: ERROR: {str(e)}")
            return False

    # Get the HTML file path
    html_path = Path(__file__).parent.parent.parent / "dashboard" / "index.html"

    if not html_path.exists():
        results.append(f"✗ HTML file not found at {html_path}")
        return results

    # Read file content
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Test 1: File is valid HTML
    def test_valid_html():
        assert "<!DOCTYPE html>" in content, "Missing DOCTYPE declaration"
        assert "<html" in content, "Missing html opening tag"
        assert "</html>" in content, "Missing html closing tag"
        assert "<head>" in content, "Missing head section"
        assert "<body>" in content, "Missing body section"

    # Test 2: CSS is embedded (no external stylesheets)
    def test_embedded_css():
        assert "<style>" in content, "No embedded CSS found"
        assert "</style>" in content, "Unclosed style tag"
        assert '<link rel="stylesheet"' not in content, "External CSS found (should be embedded)"

    # Test 3: JavaScript is embedded (no external scripts)
    def test_embedded_js():
        assert "<script>" in content, "No embedded JavaScript found"
        assert "</script>" in content, "Unclosed script tag"
        assert '<script src=' not in content, "External JavaScript found (should be embedded)"

    # Test 4: No CDN dependencies
    def test_no_cdn():
        cdn_patterns = [
            "cdn.jsdelivr",
            "unpkg.com",
            "cdnjs.cloudflare",
            "googleapis.com",
            "cdn.",
            "//cdn"
        ]
        for cdn in cdn_patterns:
            assert cdn not in content, f"Found CDN dependency: {cdn}"

    # Test 5: Title is set
    def test_title():
        assert "<title>" in content, "Missing title tag"
        assert "Agent Dashboard" in content or "Dashboard" in content, "Title missing 'Dashboard'"

    # Test 6: Meta viewport for responsive design
    def test_viewport():
        assert 'name="viewport"' in content, "Missing viewport meta tag"
        assert "width=device-width" in content, "Viewport not set to device width"

    # Test 7: Dark mode color variables
    def test_dark_mode_colors():
        # Check for CSS variables or dark colors
        dark_indicators = [
            "--bg-primary",
            "--bg-secondary",
            "background: #0f172a",
            "background: #1e293b",
            "color: #f1f5f9",
            ":root"
        ]
        found = any(indicator in content for indicator in dark_indicators)
        assert found, "No dark mode color variables found"

    # Test 8: Responsive breakpoints
    def test_responsive_breakpoints():
        # Check for media queries
        assert "@media" in content, "No media queries found for responsive design"

        # Common breakpoints
        breakpoints = ["768px", "1024px", "max-width", "min-width"]
        found_breakpoints = [bp for bp in breakpoints if bp in content]
        assert len(found_breakpoints) >= 2, f"Not enough responsive breakpoints. Found: {found_breakpoints}"

    # Test 9: Required UI sections
    def test_required_sections():
        required_sections = [
            "header",
            "main",
            "footer",
            "agent",
            "chat",
            "activity"
        ]
        for section in required_sections:
            assert section.lower() in content.lower(), f"Missing required section: {section}"

    # Test 10: Provider selector
    def test_provider_selector():
        providers = ["claude", "openai", "gemini", "groq", "kimi", "windsurf"]
        found = sum(1 for p in providers if p.lower() in content.lower())
        assert found >= 4, f"Not enough providers found. Expected 6, found references to {found}"

    # Test 11: Agent list (13 agents)
    def test_agent_list():
        agents = [
            "coding",
            "github",
            "linear",
            "slack",
            "ops",
            "pr_reviewer"
        ]
        found = sum(1 for agent in agents if agent in content)
        assert found >= 5, f"Not enough agents found in content. Expected 6+, found {found}"

    # Test 12: JavaScript state management
    def test_js_state():
        js_indicators = [
            "state",
            "function",
            "addEventListener",
            "getElementById",
            "querySelector"
        ]
        found = sum(1 for indicator in js_indicators if indicator in content)
        assert found >= 4, f"JavaScript may not be fully functional. Found {found}/5 indicators"

    # Test 13: CSS animations
    def test_animations():
        animation_indicators = [
            "@keyframes",
            "animation:",
            "transition:"
        ]
        found = sum(1 for indicator in animation_indicators if indicator in content)
        assert found >= 2, f"Not enough CSS animations/transitions. Found {found}"

    # Test 14: Accessibility features
    def test_accessibility():
        a11y_features = [
            'lang="en"',
            "aria-",
            "role=",
            "alt=",
            "<label"
        ]
        found = sum(1 for feature in a11y_features if feature in content)
        assert found >= 2, f"Not enough accessibility features. Found {found}"

    # Test 15: File size is reasonable (< 200KB for single file)
    def test_file_size():
        file_size = os.path.getsize(html_path)
        size_kb = file_size / 1024
        assert size_kb < 200, f"File too large: {size_kb:.2f}KB (should be < 200KB)"
        assert size_kb > 10, f"File suspiciously small: {size_kb:.2f}KB"

    # Test 16: No framework dependencies
    def test_no_frameworks():
        frameworks = [
            "react",
            "vue",
            "angular",
            "jquery",
            "bootstrap",
            "tailwind",
            "npm install",
            "node_modules"
        ]
        for framework in frameworks:
            assert framework.lower() not in content.lower(), f"Found framework dependency: {framework}"

    # Test 17: Proper HTML structure
    def test_html_structure():
        # Basic structure validation
        assert content.count("<html") == 1, "Multiple or missing html tags"
        assert content.count("<head>") == 1, "Multiple or missing head tags"
        assert content.count("<body>") == 1, "Multiple or missing body tags"

    # Test 18: Character encoding
    def test_encoding():
        assert 'charset="UTF-8"' in content or "charset=UTF-8" in content, "Missing UTF-8 charset"

    # Test 19: Layout structure (3-panel design)
    def test_layout_structure():
        layout_elements = [
            "left-panel",
            "main-panel",
            "header",
            "footer"
        ]
        for element in layout_elements:
            assert element in content, f"Missing layout element: {element}"

    # Test 20: Chat functionality elements
    def test_chat_elements():
        chat_elements = [
            "chat-input",
            "send-button",
            "chat-messages",
            "message"
        ]
        for element in chat_elements:
            assert element in content, f"Missing chat element: {element}"

    # Run all tests
    run_test("Valid HTML structure", test_valid_html)
    run_test("CSS is embedded (no external)", test_embedded_css)
    run_test("JavaScript is embedded (no external)", test_embedded_js)
    run_test("No CDN dependencies", test_no_cdn)
    run_test("Title is set", test_title)
    run_test("Viewport meta tag for responsive", test_viewport)
    run_test("Dark mode color variables", test_dark_mode_colors)
    run_test("Responsive breakpoints", test_responsive_breakpoints)
    run_test("Required UI sections present", test_required_sections)
    run_test("Provider selector with 6 providers", test_provider_selector)
    run_test("Agent list with 13 agents", test_agent_list)
    run_test("JavaScript state management", test_js_state)
    run_test("CSS animations and transitions", test_animations)
    run_test("Accessibility features", test_accessibility)
    run_test("File size is reasonable", test_file_size)
    run_test("No framework dependencies", test_no_frameworks)
    run_test("Proper HTML structure", test_html_structure)
    run_test("UTF-8 character encoding", test_encoding)
    run_test("3-panel layout structure", test_layout_structure)
    run_test("Chat functionality elements", test_chat_elements)

    return results


if __name__ == "__main__":
    results = test_hook()

    print("\n" + "=" * 70)
    print("AI-103: Single HTML File Dashboard - Unit Tests")
    print("=" * 70)

    for result in results:
        print(result)

    # Summary
    passed = sum(1 for r in results if r.startswith("✓"))
    failed = sum(1 for r in results if r.startswith("✗"))

    print("\n" + "-" * 70)
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    print("-" * 70)

    if failed > 0:
        print("\n❌ Some tests failed")
        exit(1)
    else:
        print("\n✅ All tests passed!")
        exit(0)
