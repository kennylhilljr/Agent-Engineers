"""Tests for Dashboard Load Time Benchmark - REQ-PERF-002.

Verifies that:
- LoadTimeChecker correctly detects external CDN dependencies.
- Load time estimation is reasonable for known file sizes.
- check_target() passes for small files and fails for huge files.
- get_html_stats() returns all required fields.
- The actual dashboard.html passes all checks (no CDN, < 2s, < 500 KB).
"""

import os
from pathlib import Path

import pytest

from dashboard.load_time_benchmark import (
    LoadTimeChecker,
    get_html_stats,
    DEFAULT_TARGET_MS,
    MAX_ALLOWED_SIZE_BYTES,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def checker():
    """Return a fresh LoadTimeChecker."""
    return LoadTimeChecker()


@pytest.fixture
def local_only_html():
    """Minimal HTML with no external dependencies."""
    return """<!DOCTYPE html>
<html>
<head>
  <title>Test</title>
  <style>body { color: red; }</style>
</head>
<body>
  <script>console.log("hello");</script>
</body>
</html>"""


@pytest.fixture
def cdn_html():
    """HTML with multiple CDN dependencies."""
    return """<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5/dist/css/bootstrap.min.css">
  <script src="https://unpkg.com/react@17/umd/react.production.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Roboto" rel="stylesheet">
</head>
<body></body>
</html>"""


@pytest.fixture
def dashboard_html_content():
    """Load the actual dashboard.html file."""
    html_path = Path(__file__).parent.parent / "dashboard.html"
    return html_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests: check_no_external_deps()
# ---------------------------------------------------------------------------

class TestCheckNoExternalDeps:
    """Tests for CDN dependency detection."""

    def test_local_only_html_returns_empty_list(self, checker, local_only_html):
        """Local-only HTML has no CDN dependencies."""
        deps = checker.check_no_external_deps(local_only_html)
        assert deps == []

    def test_cdn_html_returns_non_empty_list(self, checker, cdn_html):
        """HTML with CDN links returns at least one external URL."""
        deps = checker.check_no_external_deps(cdn_html)
        assert len(deps) > 0

    def test_jsdelivr_detected(self, checker):
        """jsdelivr.net URLs are detected."""
        html = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.0.1/dist/chart.umd.min.js"></script>'
        deps = checker.check_no_external_deps(html)
        assert any("jsdelivr" in d for d in deps)

    def test_unpkg_detected(self, checker):
        """unpkg.com URLs are detected."""
        html = '<script src="https://unpkg.com/react@17/umd/react.production.min.js"></script>'
        deps = checker.check_no_external_deps(html)
        assert any("unpkg" in d for d in deps)

    def test_cloudflare_detected(self, checker):
        """cloudflare.com URLs are detected."""
        html = '<script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>'
        deps = checker.check_no_external_deps(html)
        assert any("cloudflare" in d for d in deps)

    def test_googleapis_detected(self, checker):
        """googleapis.com URLs are detected."""
        html = '<link href="https://fonts.googleapis.com/css?family=Roboto" rel="stylesheet">'
        deps = checker.check_no_external_deps(html)
        assert any("googleapis" in d for d in deps)

    def test_empty_html_returns_empty_list(self, checker):
        """Empty string has no CDN dependencies."""
        assert checker.check_no_external_deps("") == []

    def test_relative_src_not_detected(self, checker):
        """Relative paths are not falsely flagged as CDN dependencies."""
        html = '<script src="/static/js/app.js"></script><link href="./styles.css">'
        deps = checker.check_no_external_deps(html)
        assert deps == []

    def test_inline_script_no_cdn_not_detected(self, checker):
        """Inline scripts without CDN references are not flagged."""
        html = '<script>var x = 1; console.log("https://example.com");</script>'
        # example.com is not a CDN pattern
        deps = checker.check_no_external_deps(html)
        assert deps == []

    def test_cdn_html_returns_multiple_urls(self, checker, cdn_html):
        """Multiple CDN sources are all detected."""
        deps = checker.check_no_external_deps(cdn_html)
        assert len(deps) >= 3


# ---------------------------------------------------------------------------
# Tests: estimate_load_time_ms()
# ---------------------------------------------------------------------------

class TestEstimateLoadTimeMs:
    """Tests for load time estimation."""

    def test_empty_html_returns_minimal_time(self, checker):
        """Empty HTML returns a minimal (overhead-only) load time."""
        result = checker.estimate_load_time_ms("")
        assert result == 0.0  # empty string: no transfer, no overhead either

    def test_small_file_fast_estimate(self, checker):
        """A 1 KB file on 100 Mbps estimates well under 2000ms."""
        content = "x" * 1024  # 1 KB
        result = checker.estimate_load_time_ms(content, bandwidth_mbps=100)
        assert result < 2000.0

    def test_100kb_file_estimate_reasonable(self, checker):
        """A 100 KB file on 100 Mbps estimates as a small fraction of a second."""
        content = "x" * (100 * 1024)  # 100 KB
        result = checker.estimate_load_time_ms(content, bandwidth_mbps=100)
        # 100 KB * 8 bits / (100 Mbps = 100e6 bps) = 0.008 s = 8ms + 5ms overhead = 13ms
        assert result < 100.0
        assert result >= 5.0  # at least overhead

    def test_500kb_file_estimate(self, checker):
        """A 500 KB file on 100 Mbps estimates as ~40ms."""
        content = "x" * (500 * 1024)
        result = checker.estimate_load_time_ms(content, bandwidth_mbps=100)
        # 500 KB * 8 / 100e6 * 1000 = 40ms + 5ms = 45ms
        assert 30.0 < result < 100.0

    def test_lower_bandwidth_increases_estimate(self, checker):
        """Lower bandwidth gives higher estimated load time."""
        content = "x" * (100 * 1024)
        fast = checker.estimate_load_time_ms(content, bandwidth_mbps=1000)
        slow = checker.estimate_load_time_ms(content, bandwidth_mbps=1)
        assert slow > fast

    def test_estimate_scales_with_size(self, checker):
        """Doubling the content size roughly doubles the transfer portion."""
        small = checker.estimate_load_time_ms("x" * 1000, bandwidth_mbps=100)
        large = checker.estimate_load_time_ms("x" * 2000, bandwidth_mbps=100)
        # The transfer portion should roughly double (overhead stays constant)
        assert large > small


# ---------------------------------------------------------------------------
# Tests: check_target()
# ---------------------------------------------------------------------------

class TestCheckTarget:
    """Tests for load time target verification."""

    def test_empty_html_passes_target(self, checker):
        """Empty HTML passes (trivially under target)."""
        assert checker.check_target("") is True

    def test_small_html_passes_default_target(self, checker):
        """A small HTML file passes the 2000ms default target."""
        small_html = "<html><body>Hello</body></html>"
        assert checker.check_target(small_html) is True

    def test_huge_file_fails_target(self, checker):
        """A very large file fails the 2000ms target on 100 Mbps."""
        # 300 MB of content: at 100 Mbps = 24,000 ms
        huge_html = "x" * (300 * 1024 * 1024)
        assert checker.check_target(huge_html, target_ms=2000) is False

    def test_custom_target_ms(self, checker):
        """Custom target_ms is respected."""
        # 1 KB file ~13ms on 100 Mbps
        small_html = "x" * 1024
        assert checker.check_target(small_html, target_ms=2000) is True
        assert checker.check_target(small_html, target_ms=1) is False

    def test_500kb_passes_2000ms_target(self, checker):
        """A 500 KB file (the max recommended size) passes the 2s target."""
        content = "x" * (500 * 1024)
        assert checker.check_target(content, target_ms=2000) is True


# ---------------------------------------------------------------------------
# Tests: get_html_stats()
# ---------------------------------------------------------------------------

class TestGetHtmlStats:
    """Tests for the convenience stats function."""

    def test_returns_all_required_fields(self, local_only_html):
        """get_html_stats returns all required fields."""
        stats = get_html_stats(local_only_html)
        required = {"size_bytes", "size_kb", "external_deps", "estimated_load_ms", "passes_target"}
        assert required.issubset(stats.keys())

    def test_size_bytes_matches_utf8_encoding(self, local_only_html):
        """size_bytes equals the UTF-8 encoded byte length."""
        stats = get_html_stats(local_only_html)
        expected = len(local_only_html.encode("utf-8"))
        assert stats["size_bytes"] == expected

    def test_size_kb_is_rounded(self, local_only_html):
        """size_kb is rounded to 2 decimal places."""
        stats = get_html_stats(local_only_html)
        assert isinstance(stats["size_kb"], float)
        assert stats["size_kb"] == round(stats["size_bytes"] / 1024, 2)

    def test_local_html_has_no_external_deps(self, local_only_html):
        """Local-only HTML has empty external_deps list."""
        stats = get_html_stats(local_only_html)
        assert stats["external_deps"] == []

    def test_cdn_html_has_external_deps(self, cdn_html):
        """CDN HTML has non-empty external_deps list."""
        stats = get_html_stats(cdn_html)
        assert len(stats["external_deps"]) > 0

    def test_passes_target_is_bool(self, local_only_html):
        """passes_target is a boolean value."""
        stats = get_html_stats(local_only_html)
        assert isinstance(stats["passes_target"], bool)

    def test_estimated_load_ms_is_float(self, local_only_html):
        """estimated_load_ms is a float value."""
        stats = get_html_stats(local_only_html)
        assert isinstance(stats["estimated_load_ms"], float)

    def test_empty_html_returns_zero_size(self):
        """Empty HTML string gives 0 byte size."""
        stats = get_html_stats("")
        assert stats["size_bytes"] == 0
        assert stats["size_kb"] == 0.0


# ---------------------------------------------------------------------------
# Tests: Actual dashboard.html
# ---------------------------------------------------------------------------

class TestActualDashboardHtml:
    """Integration tests that validate the real dashboard.html file."""

    def test_dashboard_html_exists(self):
        """dashboard.html exists at the expected path."""
        html_path = Path(__file__).parent.parent / "dashboard.html"
        assert html_path.exists(), f"dashboard.html not found at {html_path}"

    def test_dashboard_html_no_cdn_deps(self, checker, dashboard_html_content):
        """dashboard.html has no external CDN dependencies."""
        deps = checker.check_no_external_deps(dashboard_html_content)
        assert deps == [], (
            f"dashboard.html has {len(deps)} CDN dependency(ies): {deps[:5]}"
        )

    def test_dashboard_html_load_time_under_2s(self, checker, dashboard_html_content):
        """dashboard.html estimated load time is under 2000ms on 100 Mbps."""
        estimated_ms = checker.estimate_load_time_ms(dashboard_html_content)
        assert estimated_ms < DEFAULT_TARGET_MS, (
            f"Estimated load time {estimated_ms:.1f}ms exceeds {DEFAULT_TARGET_MS}ms target"
        )

    def test_dashboard_html_check_target_passes(self, checker, dashboard_html_content):
        """check_target() returns True for dashboard.html."""
        assert checker.check_target(dashboard_html_content) is True

    def test_dashboard_html_size_under_500kb(self, dashboard_html_content):
        """dashboard.html is smaller than 500 KB."""
        size_bytes = len(dashboard_html_content.encode("utf-8"))
        assert size_bytes < MAX_ALLOWED_SIZE_BYTES, (
            f"dashboard.html is {size_bytes / 1024:.1f} KB, exceeds 500 KB limit"
        )

    def test_dashboard_html_stats_passes_target(self, dashboard_html_content):
        """get_html_stats() reports passes_target=True for dashboard.html."""
        stats = get_html_stats(dashboard_html_content)
        assert stats["passes_target"] is True, (
            f"Stats: {stats}"
        )

    def test_dashboard_html_stats_no_external_deps(self, dashboard_html_content):
        """get_html_stats() shows no external dependencies for dashboard.html."""
        stats = get_html_stats(dashboard_html_content)
        assert stats["external_deps"] == [], (
            f"Unexpected external deps: {stats['external_deps'][:5]}"
        )

    def test_dashboard_html_stats_has_positive_size(self, dashboard_html_content):
        """dashboard.html is non-empty (size > 0)."""
        stats = get_html_stats(dashboard_html_content)
        assert stats["size_bytes"] > 0
        assert stats["size_kb"] > 0.0
