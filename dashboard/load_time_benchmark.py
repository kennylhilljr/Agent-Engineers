"""Dashboard Load Time Benchmark - REQ-PERF-002.

Provides utilities to verify that dashboard.html has no external CDN
dependencies and will load in under 2 seconds on a 100 Mbps local connection.

Classes:
    LoadTimeChecker -- Detects CDN deps and estimates load time from file size

Functions:
    get_html_stats(html_content) -- Returns a summary dict for a given HTML string
"""

import re
from typing import List


# Patterns that indicate external CDN dependencies
_CDN_PATTERNS = [
    r'https?://cdn\.',
    r'https?://[^"\']*jsdelivr\.net',
    r'https?://[^"\']*unpkg\.com',
    r'https?://[^"\']*cloudflare\.com',
    r'https?://[^"\']*googleapis\.com',
    r'https?://[^"\']*gstatic\.com',
    r'https?://[^"\']*bootstrapcdn\.com',
    r'https?://[^"\']*cdnjs\.com',
]

# Combined regex compiled once for performance
_CDN_REGEX = re.compile('|'.join(_CDN_PATTERNS), re.IGNORECASE)

# Target load time in milliseconds (REQ-PERF-002)
DEFAULT_TARGET_MS: float = 2000.0

# Maximum acceptable file size (500 KB = 512,000 bytes)
MAX_ALLOWED_SIZE_BYTES: int = 500 * 1024  # 500 KB


class LoadTimeChecker:
    """Check dashboard HTML load time and external dependency requirements.

    Provides three core checks:
    1. ``check_no_external_deps``  — scans HTML for CDN/external URLs
    2. ``estimate_load_time_ms``   — estimates load time from file size
    3. ``check_target``            — returns True if estimated time < target

    All methods are stateless and accept raw HTML strings.
    """

    def check_no_external_deps(self, html_content: str) -> List[str]:
        """Scan HTML for external CDN dependency URLs.

        Looks for ``<script src>``, ``<link href>``, ``<img src>``, ``@import``
        and any raw ``https://`` URL that points to a known CDN domain.

        Args:
            html_content: Full HTML text to inspect.

        Returns:
            List of external URLs found.  An empty list means the HTML is
            self-contained (passes the check).
        """
        if not html_content:
            return []

        found: List[str] = []
        seen = set()
        for match in _CDN_REGEX.finditer(html_content):
            # Extract the full URL (up to a quote or whitespace)
            start = match.start()
            # Grab the URL token from the full string
            url_match = re.match(r'[^\s"\'<>]+', html_content[start:])
            url = url_match.group(0) if url_match else match.group(0)
            if url not in seen:
                seen.add(url)
                found.append(url)
        return found

    def estimate_load_time_ms(
        self,
        html_content: str,
        bandwidth_mbps: float = 100.0,
    ) -> float:
        """Estimate local page load time based on HTML file size.

        The model is a simple bandwidth calculation:
            load_time_ms = (size_bytes * 8 / (bandwidth_mbps * 1e6)) * 1000

        A fixed 5 ms local-server overhead is added to account for TCP handshake
        and HTTP round-trip on localhost.

        Args:
            html_content: Full HTML text.
            bandwidth_mbps: Assumed network bandwidth in Mbps (default: 100).

        Returns:
            Estimated load time in milliseconds (float).
        """
        if not html_content:
            return 0.0

        size_bytes = len(html_content.encode("utf-8"))
        # bits / (bits per second) -> seconds -> milliseconds
        transfer_ms = (size_bytes * 8) / (bandwidth_mbps * 1_000_000) * 1000.0
        # Add a fixed overhead for localhost HTTP round-trip
        overhead_ms = 5.0
        return transfer_ms + overhead_ms

    def check_target(
        self,
        html_content: str,
        target_ms: float = DEFAULT_TARGET_MS,
    ) -> bool:
        """Return True if estimated load time is below *target_ms*.

        Args:
            html_content: Full HTML text.
            target_ms: Load time budget in milliseconds (default: 2000).

        Returns:
            True when estimated load time <= target_ms, False otherwise.
        """
        return self.estimate_load_time_ms(html_content) <= target_ms


def get_html_stats(html_content: str) -> dict:
    """Return a summary dict of HTML load-time metrics.

    Convenience wrapper that creates a :class:`LoadTimeChecker` and runs all
    checks, returning a single dict suitable for logging or API responses.

    Args:
        html_content: Full HTML text to analyse.

    Returns:
        Dict with keys:
            size_bytes (int):           UTF-8 encoded byte length
            size_kb (float):            size in kilobytes (rounded to 2 dp)
            external_deps (list[str]):  CDN URLs found (empty = pass)
            estimated_load_ms (float):  estimated 100 Mbps load time
            passes_target (bool):       True if estimated_load_ms <= 2000 ms
    """
    checker = LoadTimeChecker()
    size_bytes = len(html_content.encode("utf-8")) if html_content else 0
    size_kb = round(size_bytes / 1024, 2)
    external_deps = checker.check_no_external_deps(html_content)
    estimated_load_ms = checker.estimate_load_time_ms(html_content)
    passes_target = checker.check_target(html_content)

    return {
        "size_bytes": size_bytes,
        "size_kb": size_kb,
        "external_deps": external_deps,
        "estimated_load_ms": estimated_load_ms,
        "passes_target": passes_target,
    }
