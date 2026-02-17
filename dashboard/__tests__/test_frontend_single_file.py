"""
Tests for AI-167: REQ-TECH-002 - Frontend Single HTML File compliance.

Validates that dashboard/dashboard.html meets the acceptance criteria:
- Single HTML file (no build step)
- Embedded CSS and JS
- No external HTTP dependencies (no CDN links, no npm)
- Responsive design (viewport meta tag)
- File size is reasonable (< 2MB)
- Basic accessibility (aria-labels, roles)
"""
import os
import re
import pytest

DASHBOARD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "dashboard.html"
)


@pytest.fixture(scope="module")
def dashboard_content():
    """Load the dashboard.html file content once for all tests."""
    assert os.path.isfile(DASHBOARD_PATH), (
        f"dashboard.html not found at {DASHBOARD_PATH}"
    )
    with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
        return f.read()


class TestSingleHtmlFile:
    """Tests that verify the file is a single self-contained HTML file."""

    def test_file_exists(self):
        """dashboard.html must exist at the expected path."""
        assert os.path.isfile(DASHBOARD_PATH), (
            f"dashboard.html not found at {DASHBOARD_PATH}"
        )

    def test_file_is_html(self, dashboard_content):
        """File must start with a valid HTML doctype declaration."""
        assert dashboard_content.strip().upper().startswith("<!DOCTYPE HTML"), (
            "File does not start with <!DOCTYPE HTML>"
        )

    def test_file_size_under_2mb(self):
        """File must be under 2MB in size."""
        size_bytes = os.path.getsize(DASHBOARD_PATH)
        max_bytes = 2 * 1024 * 1024  # 2MB
        assert size_bytes < max_bytes, (
            f"File size {size_bytes} bytes exceeds 2MB limit ({max_bytes} bytes)"
        )

    def test_no_external_script_src(self, dashboard_content):
        """No <script src='http...'> tags (no CDN script dependencies)."""
        matches = re.findall(
            r'<script[^>]+src=["\']https?://', dashboard_content, re.IGNORECASE
        )
        assert len(matches) == 0, (
            f"Found external script src tags: {matches}"
        )

    def test_no_external_link_href(self, dashboard_content):
        """No <link href='http...'> tags (no external stylesheet dependencies)."""
        matches = re.findall(
            r'<link[^>]+href=["\']https?://', dashboard_content, re.IGNORECASE
        )
        assert len(matches) == 0, (
            f"Found external link href tags: {matches}"
        )

    def test_no_external_img_src(self, dashboard_content):
        """No <img src='http...'> tags pointing to external resources."""
        matches = re.findall(
            r'<img[^>]+src=["\']https?://', dashboard_content, re.IGNORECASE
        )
        assert len(matches) == 0, (
            f"Found external img src tags: {matches}"
        )


class TestEmbeddedAssets:
    """Tests that CSS and JS are embedded, not externally loaded."""

    def test_has_embedded_style_tag(self, dashboard_content):
        """File must have at least one <style> block with content."""
        style_blocks = re.findall(
            r'<style[^>]*>(.*?)</style>', dashboard_content, re.DOTALL | re.IGNORECASE
        )
        assert len(style_blocks) >= 1, "No <style> blocks found"
        # At least one block must have non-trivial CSS content
        non_empty = [b for b in style_blocks if len(b.strip()) > 50]
        assert len(non_empty) >= 1, (
            "No <style> block with substantial CSS content found"
        )

    def test_has_embedded_script_tag(self, dashboard_content):
        """File must have at least one inline <script> block (no src attribute)."""
        # Find script tags WITHOUT a src attribute that have content
        inline_scripts = re.findall(
            r'<script(?![^>]*\bsrc\b)[^>]*>(.*?)</script>',
            dashboard_content,
            re.DOTALL | re.IGNORECASE,
        )
        assert len(inline_scripts) >= 1, "No inline <script> blocks found"
        non_empty = [s for s in inline_scripts if len(s.strip()) > 50]
        assert len(non_empty) >= 1, (
            "No inline <script> block with substantial JS content found"
        )

    def test_chartjs_is_inlined(self, dashboard_content):
        """Chart.js must be inlined (no CDN script tag for chart.js)."""
        cdn_pattern = re.findall(
            r'<script[^>]+src=["\'][^"\']*chart[^"\']*["\']',
            dashboard_content,
            re.IGNORECASE,
        )
        assert len(cdn_pattern) == 0, (
            f"Chart.js still loaded from CDN: {cdn_pattern}"
        )
        # Verify Chart.js constructor code is present inline
        assert "new Chart(" in dashboard_content, (
            "Chart.js usage (new Chart(...)) not found in file — may not be inlined"
        )


class TestResponsiveDesign:
    """Tests that verify responsive design requirements."""

    def test_viewport_meta_tag_present(self, dashboard_content):
        """A viewport meta tag must be present for mobile responsiveness."""
        assert re.search(
            r'<meta[^>]+name=["\']viewport["\']', dashboard_content, re.IGNORECASE
        ), "No viewport meta tag found"

    def test_viewport_meta_has_width_device_width(self, dashboard_content):
        """The viewport meta tag must set width=device-width."""
        match = re.search(
            r'<meta[^>]+name=["\']viewport["\'][^>]*content=["\']([^"\']+)["\']',
            dashboard_content,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*name=["\']viewport["\']',
                dashboard_content,
                re.IGNORECASE,
            )
        assert match, "Could not find viewport meta tag content"
        content_val = match.group(1)
        assert "width=device-width" in content_val, (
            f"Viewport meta content missing 'width=device-width': {content_val}"
        )

    def test_has_media_queries(self, dashboard_content):
        """CSS must include at least one @media query for responsive layout."""
        media_queries = re.findall(r'@media\s*\(', dashboard_content)
        assert len(media_queries) >= 1, (
            "No CSS @media queries found — responsive design may be missing"
        )


class TestAccessibility:
    """Tests for basic accessibility compliance."""

    def test_html_has_lang_attribute(self, dashboard_content):
        """The <html> element must have a lang attribute."""
        assert re.search(
            r'<html[^>]+lang=["\'][a-z]{2}', dashboard_content, re.IGNORECASE
        ), "<html> element is missing a lang attribute"

    def test_images_have_alt_attributes(self, dashboard_content):
        """All <img> tags must have an alt attribute."""
        img_tags = re.findall(r'<img[^>]+>', dashboard_content, re.IGNORECASE)
        missing_alt = [tag for tag in img_tags if not re.search(r'\balt=', tag, re.IGNORECASE)]
        assert len(missing_alt) == 0, (
            f"Found <img> tags missing alt attribute: {missing_alt}"
        )

    def test_inputs_have_labels_or_aria(self, dashboard_content):
        """
        All visible <input> elements must have aria-label, aria-labelledby,
        or be associated with a <label> via id/for pairing.
        """
        input_tags = re.finditer(
            r'<input([^>]*)>', dashboard_content, re.IGNORECASE
        )
        violations = []
        for m in input_tags:
            attrs = m.group(1)
            # Skip hidden inputs
            if re.search(r'type=["\']hidden["\']', attrs, re.IGNORECASE):
                continue
            has_aria_label = bool(re.search(r'aria-label=', attrs, re.IGNORECASE))
            has_aria_labelledby = bool(re.search(r'aria-labelledby=', attrs, re.IGNORECASE))
            # Check if it has an id that a <label for="..."> references
            id_match = re.search(r'\bid=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            has_label_for = False
            if id_match:
                input_id = id_match.group(1)
                has_label_for = bool(
                    re.search(
                        rf'<label[^>]+for=["\'{re.escape(input_id)}["\']',
                        dashboard_content,
                        re.IGNORECASE,
                    )
                )
            if not (has_aria_label or has_aria_labelledby or has_label_for):
                violations.append(m.group(0)[:120])
        assert len(violations) == 0, (
            f"Found <input> elements without accessible labels:\n"
            + "\n".join(violations)
        )

    def test_buttons_have_accessible_names(self, dashboard_content):
        """
        Buttons must have either visible text content or an aria-label.
        """
        button_blocks = re.findall(
            r'<button([^>]*)>(.*?)</button>', dashboard_content, re.DOTALL | re.IGNORECASE
        )
        violations = []
        for attrs, inner in button_blocks:
            has_aria_label = bool(re.search(r'aria-label=', attrs, re.IGNORECASE))
            visible_text = re.sub(r'<[^>]+>', '', inner).strip()
            if not has_aria_label and not visible_text:
                violations.append(f"<button{attrs[:80]}>...")
        assert len(violations) == 0, (
            f"Found buttons without accessible names:\n" + "\n".join(violations)
        )

    def test_role_status_present_for_feedback(self, dashboard_content):
        """Live regions for feedback messages should have role='status'."""
        assert 'role="status"' in dashboard_content or "role='status'" in dashboard_content, (
            "No element with role='status' found — feedback regions may not be announced"
        )
