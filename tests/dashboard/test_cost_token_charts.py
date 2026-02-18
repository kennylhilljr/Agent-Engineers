"""
Tests for AI-149: REQ-METRICS-003: Implement Cost and Token Charts

Verifies:
- charts-section HTML exists with 3 chart containers
- CSS classes for .chart-container, .chart-title, .chart-area
- mockChartData has correct structure (tokensByAgent, costTrend, successRates)
- window.mockChartData exposed
- renderTokenUsageChart() function exists and is window-exposed
- renderCostTrendChart() function exists and is window-exposed
- renderSuccessRateChart() function exists and is window-exposed
- renderAllCharts() function exists, is window-exposed, accepts data parameter
- loadCharts() async function exists and is window-exposed
- init() calls renderAllCharts()
- Charts use SVG with viewBox for responsiveness
- Color-coding in success rate chart
"""
import pytest
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Test Group 1: Charts HTML Structure
# ============================================================

class TestChartsHTML:
    """Verify the charts section HTML exists and has correct structure."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_charts_section_exists(self, html_content):
        """charts-section element must exist."""
        assert 'id="charts-section"' in html_content

    def test_charts_section_is_panel_section(self, html_content):
        """charts-section must have panel-section class."""
        assert 'class="panel-section charts-section"' in html_content or \
               'class="panel-section' in html_content and 'id="charts-section"' in html_content

    def test_token_usage_chart_container_exists(self, html_content):
        """token-usage-chart-container element must exist."""
        assert 'id="token-usage-chart-container"' in html_content

    def test_cost_trend_chart_container_exists(self, html_content):
        """cost-trend-chart-container element must exist."""
        assert 'id="cost-trend-chart-container"' in html_content

    def test_success_rate_chart_container_exists(self, html_content):
        """success-rate-chart-container element must exist."""
        assert 'id="success-rate-chart-container"' in html_content

    def test_token_usage_chart_area_exists(self, html_content):
        """token-usage-chart area element must exist."""
        assert 'id="token-usage-chart"' in html_content

    def test_cost_trend_chart_area_exists(self, html_content):
        """cost-trend-chart area element must exist."""
        assert 'id="cost-trend-chart"' in html_content

    def test_success_rate_chart_area_exists(self, html_content):
        """success-rate-chart area element must exist."""
        assert 'id="success-rate-chart"' in html_content

    def test_analytics_charts_title_exists(self, html_content):
        """Analytics Charts heading must exist."""
        assert 'Analytics Charts' in html_content

    def test_token_usage_chart_title_exists(self, html_content):
        """'Token Usage by Agent' title must be present."""
        assert 'Token Usage by Agent' in html_content

    def test_cost_trend_chart_title_exists(self, html_content):
        """'Cost Trend' title must be present."""
        assert 'Cost Trend' in html_content

    def test_success_rate_chart_title_exists(self, html_content):
        """'Success Rate by Agent' title must be present."""
        assert 'Success Rate by Agent' in html_content

    def test_three_chart_containers_present(self, html_content):
        """Exactly 3 chart containers must be present."""
        count = html_content.count('class="chart-container"')
        assert count >= 3


# ============================================================
# Test Group 2: Charts CSS
# ============================================================

class TestChartsCSS:
    """Verify CSS classes for charts are defined."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_chart_container_css_exists(self, html_content):
        """.chart-container CSS rule must be defined."""
        assert '.chart-container' in html_content

    def test_chart_title_css_exists(self, html_content):
        """.chart-title CSS rule must be defined."""
        assert '.chart-title' in html_content

    def test_chart_area_css_exists(self, html_content):
        """.chart-area CSS rule must be defined."""
        assert '.chart-area' in html_content

    def test_chart_bar_css_exists(self, html_content):
        """.chart-bar CSS rule must be defined."""
        assert '.chart-bar' in html_content

    def test_chart_bar_label_css_exists(self, html_content):
        """.chart-bar-label CSS rule must be defined."""
        assert '.chart-bar-label' in html_content

    def test_chart_line_css_exists(self, html_content):
        """.chart-line CSS rule must be defined."""
        assert '.chart-line' in html_content

    def test_chart_axis_css_exists(self, html_content):
        """.chart-axis CSS rule must be defined."""
        assert '.chart-axis' in html_content

    def test_chart_area_width_100(self, html_content):
        """Chart area must have responsive width: 100%."""
        # chart-area svg should have width: 100%
        assert 'width: 100%' in html_content or "width='100%'" in html_content or 'width="100%"' in html_content

    def test_charts_section_css_exists(self, html_content):
        """.charts-section CSS rule must be defined."""
        assert '.charts-section' in html_content

    def test_chart_dot_css_exists(self, html_content):
        """.chart-dot CSS rule must be defined."""
        assert '.chart-dot' in html_content

    def test_responsive_media_query_for_charts(self, html_content):
        """Charts must have mobile responsive media query."""
        # The chart-area overflow-x: scroll should be in a media query
        assert 'overflow-x' in html_content


# ============================================================
# Test Group 3: Mock Chart Data
# ============================================================

class TestMockChartData:
    """Verify mockChartData has correct structure."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_mock_chart_data_defined(self, html_content):
        """mockChartData must be defined."""
        assert 'const mockChartData' in html_content or 'mockChartData =' in html_content

    def test_window_mock_chart_data_exposed(self, html_content):
        """window.mockChartData must be exposed."""
        assert 'window.mockChartData' in html_content

    def test_mock_has_tokens_by_agent(self, html_content):
        """mockChartData must have tokensByAgent array."""
        assert 'tokensByAgent' in html_content

    def test_mock_has_cost_trend(self, html_content):
        """mockChartData must have costTrend array."""
        assert 'costTrend' in html_content

    def test_mock_has_success_rates(self, html_content):
        """mockChartData must have successRates array."""
        assert 'successRates' in html_content

    def test_tokens_by_agent_has_name_field(self, html_content):
        """tokensByAgent items must have name field."""
        # Find the tokensByAgent block and verify it has 'name' entries
        idx = html_content.find('tokensByAgent')
        assert idx > 0
        block = html_content[idx:idx+400]
        assert 'name:' in block

    def test_tokens_by_agent_has_tokens_field(self, html_content):
        """tokensByAgent items must have tokens field."""
        idx = html_content.find('tokensByAgent')
        assert idx > 0
        block = html_content[idx:idx+400]
        assert 'tokens:' in block

    def test_cost_trend_has_session_field(self, html_content):
        """costTrend items must have session field."""
        idx = html_content.find('costTrend')
        assert idx > 0
        block = html_content[idx:idx+400]
        assert 'session:' in block

    def test_cost_trend_has_cost_field(self, html_content):
        """costTrend items must have cost field."""
        idx = html_content.find('costTrend')
        assert idx > 0
        block = html_content[idx:idx+400]
        assert 'cost:' in block

    def test_success_rates_has_name_field(self, html_content):
        """successRates items must have name field."""
        idx = html_content.find('successRates')
        assert idx > 0
        block = html_content[idx:idx+400]
        assert 'name:' in block

    def test_success_rates_has_rate_field(self, html_content):
        """successRates items must have rate field."""
        idx = html_content.find('successRates')
        assert idx > 0
        block = html_content[idx:idx+400]
        assert 'rate:' in block

    def test_mock_data_has_multiple_agents(self, html_content):
        """Mock tokensByAgent should have entries for multiple agents."""
        idx = html_content.find('tokensByAgent')
        assert idx > 0
        # Count name entries in the block up to successRates
        end_idx = html_content.find('successRates', idx)
        block = html_content[idx:end_idx]
        names = re.findall(r"name:\s*'[^']+'", block)
        assert len(names) >= 5, f"Expected at least 5 agents, found {len(names)}"


# ============================================================
# Test Group 4: renderTokenUsageChart Function
# ============================================================

class TestRenderTokenUsageChart:
    """Verify renderTokenUsageChart() function is properly implemented."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_token_usage_chart_function_exists(self, html_content):
        """renderTokenUsageChart function must be defined."""
        assert 'function renderTokenUsageChart' in html_content

    def test_render_token_usage_chart_window_exposed(self, html_content):
        """window.renderTokenUsageChart must be exposed."""
        assert 'window.renderTokenUsageChart' in html_content

    def test_render_token_usage_chart_returns_svg(self, html_content):
        """Function must produce an SVG element."""
        idx = html_content.find('function renderTokenUsageChart')
        end = html_content.find('window.renderTokenUsageChart', idx)
        block = html_content[idx:end]
        assert '<svg' in block

    def test_render_token_usage_chart_uses_viewbox(self, html_content):
        """SVG must use viewBox for responsiveness."""
        idx = html_content.find('function renderTokenUsageChart')
        end = html_content.find('window.renderTokenUsageChart', idx)
        block = html_content[idx:end]
        assert 'viewBox' in block

    def test_render_token_usage_chart_uses_rect(self, html_content):
        """Function must include rect elements for bars."""
        idx = html_content.find('function renderTokenUsageChart')
        end = html_content.find('window.renderTokenUsageChart', idx)
        block = html_content[idx:end]
        assert '<rect' in block

    def test_render_token_usage_chart_includes_labels(self, html_content):
        """Function must include text elements for agent name labels."""
        idx = html_content.find('function renderTokenUsageChart')
        end = html_content.find('window.renderTokenUsageChart', idx)
        block = html_content[idx:end]
        assert '<text' in block

    def test_render_token_usage_chart_sorted_descending(self, html_content):
        """Function must sort data descending."""
        idx = html_content.find('function renderTokenUsageChart')
        end = html_content.find('window.renderTokenUsageChart', idx)
        block = html_content[idx:end]
        assert 'sort' in block and ('b.tokens - a.tokens' in block or 'b.tokens' in block)

    def test_render_token_usage_chart_inserts_into_dom(self, html_content):
        """Function must insert SVG into #token-usage-chart element."""
        idx = html_content.find('function renderTokenUsageChart')
        end = html_content.find('window.renderTokenUsageChart', idx)
        block = html_content[idx:end]
        assert 'token-usage-chart' in block

    def test_render_token_usage_chart_caps_to_10(self, html_content):
        """Function must cap at top 10 agents."""
        idx = html_content.find('function renderTokenUsageChart')
        end = html_content.find('window.renderTokenUsageChart', idx)
        block = html_content[idx:end]
        assert '10' in block or 'slice(0, 10)' in block

    def test_render_token_usage_chart_uses_accent_blue(self, html_content):
        """Function bars must use the accent blue color."""
        idx = html_content.find('function renderTokenUsageChart')
        end = html_content.find('window.renderTokenUsageChart', idx)
        block = html_content[idx:end]
        # Should reference the blue color
        assert '#3b82f6' in block or 'accent-blue' in block or 'fill=' in block


# ============================================================
# Test Group 5: renderCostTrendChart Function
# ============================================================

class TestRenderCostTrendChart:
    """Verify renderCostTrendChart() function is properly implemented."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_cost_trend_chart_function_exists(self, html_content):
        """renderCostTrendChart function must be defined."""
        assert 'function renderCostTrendChart' in html_content

    def test_render_cost_trend_chart_window_exposed(self, html_content):
        """window.renderCostTrendChart must be exposed."""
        assert 'window.renderCostTrendChart' in html_content

    def test_render_cost_trend_chart_returns_svg(self, html_content):
        """Function must produce an SVG element."""
        idx = html_content.find('function renderCostTrendChart')
        end = html_content.find('window.renderCostTrendChart', idx)
        block = html_content[idx:end]
        assert '<svg' in block

    def test_render_cost_trend_chart_uses_viewbox(self, html_content):
        """SVG must use viewBox for responsiveness."""
        idx = html_content.find('function renderCostTrendChart')
        end = html_content.find('window.renderCostTrendChart', idx)
        block = html_content[idx:end]
        assert 'viewBox' in block

    def test_render_cost_trend_chart_uses_polyline(self, html_content):
        """Function must use polyline or path for line chart."""
        idx = html_content.find('function renderCostTrendChart')
        end = html_content.find('window.renderCostTrendChart', idx)
        block = html_content[idx:end]
        assert 'polyline' in block or '<path' in block

    def test_render_cost_trend_chart_has_grid_lines(self, html_content):
        """Function must include grid lines for readability."""
        idx = html_content.find('function renderCostTrendChart')
        end = html_content.find('window.renderCostTrendChart', idx)
        block = html_content[idx:end]
        assert 'grid' in block.lower() or 'stroke-dasharray' in block

    def test_render_cost_trend_chart_shows_cost_values(self, html_content):
        """Function must display cost values ($ sign or .toFixed)."""
        idx = html_content.find('function renderCostTrendChart')
        end = html_content.find('window.renderCostTrendChart', idx)
        block = html_content[idx:end]
        assert '$' in block or '.toFixed' in block

    def test_render_cost_trend_chart_includes_session_labels(self, html_content):
        """Function must render session axis labels."""
        idx = html_content.find('function renderCostTrendChart')
        end = html_content.find('window.renderCostTrendChart', idx)
        block = html_content[idx:end]
        assert 'd.session' in block or 'session' in block

    def test_render_cost_trend_chart_has_axes(self, html_content):
        """Function must render x and y axes."""
        idx = html_content.find('function renderCostTrendChart')
        end = html_content.find('window.renderCostTrendChart', idx)
        block = html_content[idx:end]
        assert 'xAxis' in block or 'yAxis' in block or '<line' in block

    def test_render_cost_trend_chart_inserts_into_dom(self, html_content):
        """Function must insert SVG into #cost-trend-chart element."""
        idx = html_content.find('function renderCostTrendChart')
        end = html_content.find('window.renderCostTrendChart', idx)
        block = html_content[idx:end]
        assert 'cost-trend-chart' in block


# ============================================================
# Test Group 6: renderSuccessRateChart Function
# ============================================================

class TestRenderSuccessRateChart:
    """Verify renderSuccessRateChart() function is properly implemented."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_success_rate_chart_function_exists(self, html_content):
        """renderSuccessRateChart function must be defined."""
        assert 'function renderSuccessRateChart' in html_content

    def test_render_success_rate_chart_window_exposed(self, html_content):
        """window.renderSuccessRateChart must be exposed."""
        assert 'window.renderSuccessRateChart' in html_content

    def test_render_success_rate_chart_returns_svg(self, html_content):
        """Function must produce an SVG element."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert '<svg' in block

    def test_render_success_rate_chart_uses_viewbox(self, html_content):
        """SVG must use viewBox for responsiveness."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert 'viewBox' in block

    def test_render_success_rate_chart_uses_rect(self, html_content):
        """Function must include rect elements for bars."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert '<rect' in block

    def test_render_success_rate_chart_green_color(self, html_content):
        """Function must use green color for >80% success rate."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert '#10b981' in block or 'accent-green' in block

    def test_render_success_rate_chart_yellow_color(self, html_content):
        """Function must use yellow color for 50-80% success rate."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert '#f59e0b' in block or 'accent-yellow' in block or 'yellow' in block.lower()

    def test_render_success_rate_chart_red_color(self, html_content):
        """Function must use red color for <50% success rate."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert '#ef4444' in block or 'accent-red' in block

    def test_render_success_rate_chart_color_thresholds(self, html_content):
        """Function must use conditional logic for color coding."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert '80' in block and '50' in block

    def test_render_success_rate_chart_shows_rate_value(self, html_content):
        """Function must display rate values on bars."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert 'rate' in block and ('%' in block or 'item.rate' in block)

    def test_render_success_rate_chart_inserts_into_dom(self, html_content):
        """Function must insert SVG into #success-rate-chart element."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert 'success-rate-chart' in block

    def test_render_success_rate_chart_sorted_descending(self, html_content):
        """Function must sort agents by rate descending."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert 'sort' in block and ('b.rate' in block or 'rate' in block)


# ============================================================
# Test Group 7: renderAllCharts Function
# ============================================================

class TestRenderAllCharts:
    """Verify renderAllCharts() function is properly implemented."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_all_charts_function_exists(self, html_content):
        """renderAllCharts function must be defined."""
        assert 'function renderAllCharts' in html_content

    def test_render_all_charts_window_exposed(self, html_content):
        """window.renderAllCharts must be exposed."""
        assert 'window.renderAllCharts' in html_content

    def test_render_all_charts_calls_token_usage(self, html_content):
        """renderAllCharts must call renderTokenUsageChart."""
        idx = html_content.find('function renderAllCharts')
        end = html_content.find('window.renderAllCharts', idx)
        block = html_content[idx:end]
        assert 'renderTokenUsageChart' in block

    def test_render_all_charts_calls_cost_trend(self, html_content):
        """renderAllCharts must call renderCostTrendChart."""
        idx = html_content.find('function renderAllCharts')
        end = html_content.find('window.renderAllCharts', idx)
        block = html_content[idx:end]
        assert 'renderCostTrendChart' in block

    def test_render_all_charts_calls_success_rate(self, html_content):
        """renderAllCharts must call renderSuccessRateChart."""
        idx = html_content.find('function renderAllCharts')
        end = html_content.find('window.renderAllCharts', idx)
        block = html_content[idx:end]
        assert 'renderSuccessRateChart' in block

    def test_render_all_charts_accepts_data_param(self, html_content):
        """renderAllCharts must accept a data parameter."""
        idx = html_content.find('function renderAllCharts')
        end = html_content.find('window.renderAllCharts', idx)
        block = html_content[idx:end]
        # Should have parameter in function signature
        assert re.search(r'function renderAllCharts\s*\(\s*\w+', block)

    def test_render_all_charts_uses_mock_as_fallback(self, html_content):
        """renderAllCharts must use mockChartData as fallback."""
        idx = html_content.find('function renderAllCharts')
        end = html_content.find('window.renderAllCharts', idx)
        block = html_content[idx:end]
        assert 'mockChartData' in block


# ============================================================
# Test Group 8: loadCharts Async Function
# ============================================================

class TestLoadChartsFunction:
    """Verify loadCharts() async function is properly implemented."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_load_charts_function_exists(self, html_content):
        """loadCharts function must be defined."""
        assert 'function loadCharts' in html_content

    def test_load_charts_window_exposed(self, html_content):
        """window.loadCharts must be exposed."""
        assert 'window.loadCharts' in html_content

    def test_load_charts_is_async(self, html_content):
        """loadCharts must be an async function."""
        assert 'async function loadCharts' in html_content

    def test_load_charts_fetches_api_metrics(self, html_content):
        """loadCharts must try to fetch /api/metrics."""
        idx = html_content.find('function loadCharts')
        end = html_content.find('window.loadCharts', idx)
        block = html_content[idx:end]
        assert '/api/metrics' in block

    def test_load_charts_has_try_catch(self, html_content):
        """loadCharts must have try/catch for error handling."""
        idx = html_content.find('function loadCharts')
        end = html_content.find('window.loadCharts', idx)
        block = html_content[idx:end]
        assert 'try' in block and 'catch' in block

    def test_load_charts_falls_back_to_mock(self, html_content):
        """loadCharts must fall back to mockChartData on failure."""
        idx = html_content.find('function loadCharts')
        end = html_content.find('window.loadCharts', idx)
        block = html_content[idx:end]
        assert 'mockChartData' in block

    def test_load_charts_calls_render_all_charts(self, html_content):
        """loadCharts must call renderAllCharts."""
        idx = html_content.find('function loadCharts')
        end = html_content.find('window.loadCharts', idx)
        block = html_content[idx:end]
        assert 'renderAllCharts' in block

    def test_load_charts_uses_fetch(self, html_content):
        """loadCharts must use fetch() API."""
        idx = html_content.find('function loadCharts')
        end = html_content.find('window.loadCharts', idx)
        block = html_content[idx:end]
        assert 'fetch(' in block


# ============================================================
# Test Group 9: Charts in init() Function
# ============================================================

class TestChartsInInit:
    """Verify chart rendering is called in init()."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_render_all_charts_called_in_init(self, html_content):
        """renderAllCharts() must be called in init()."""
        idx = html_content.find('function init(')
        assert idx > 0
        end = html_content.find('\n        }', idx + len('function init('))
        init_block = html_content[idx:end + 10]
        assert 'renderAllCharts' in init_block or 'loadCharts' in init_block

    def test_init_calls_charts_after_agents(self, html_content):
        """Charts must be initialized after agents are rendered."""
        idx = html_content.find('function init(')
        assert idx > 0
        # renderAllCharts or loadCharts should come after renderAgents
        render_agents_pos = html_content.find('renderAgents()', idx)
        render_charts_pos = html_content.find('renderAllCharts()', idx)
        if render_charts_pos < 0:
            render_charts_pos = html_content.find('loadCharts()', idx)
        assert render_agents_pos > 0 and render_charts_pos > render_agents_pos

    def test_charts_section_rendered_on_init(self, html_content):
        """charts-section should be in the DOM so JS can populate it."""
        # Verify charts-section appears in HTML (not in JS template strings)
        # It should be a static HTML element, not just rendered dynamically
        assert 'id="charts-section"' in html_content
        # And the init function should call renderAllCharts
        idx = html_content.find('function init(')
        end = html_content.rfind('</script>')
        init_to_end = html_content[idx:end]
        assert 'renderAllCharts' in init_to_end or 'loadCharts' in init_to_end


# ============================================================
# Test Group 10: SVG Responsiveness
# ============================================================

class TestChartsSVGResponsiveness:
    """Verify SVG charts are responsive."""

    @pytest.fixture(scope='class')
    def html_content(self):
        return (PROJECT_ROOT / 'dashboard' / 'index.html').read_text(encoding='utf-8')

    def test_token_chart_svg_has_width_100_percent(self, html_content):
        """Token usage chart SVG must have width='100%'."""
        idx = html_content.find('function renderTokenUsageChart')
        end = html_content.find('window.renderTokenUsageChart', idx)
        block = html_content[idx:end]
        assert 'width="100%"' in block or "width='100%'" in block

    def test_cost_chart_svg_has_width_100_percent(self, html_content):
        """Cost trend chart SVG must have width='100%'."""
        idx = html_content.find('function renderCostTrendChart')
        end = html_content.find('window.renderCostTrendChart', idx)
        block = html_content[idx:end]
        assert 'width="100%"' in block or "width='100%'" in block

    def test_success_chart_svg_has_width_100_percent(self, html_content):
        """Success rate chart SVG must have width='100%'."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert 'width="100%"' in block or "width='100%'" in block

    def test_token_chart_svg_height_auto(self, html_content):
        """Token usage chart SVG must have height='auto'."""
        idx = html_content.find('function renderTokenUsageChart')
        end = html_content.find('window.renderTokenUsageChart', idx)
        block = html_content[idx:end]
        assert 'height="auto"' in block or "height='auto'" in block

    def test_cost_chart_svg_height_auto(self, html_content):
        """Cost trend chart SVG must have height='auto'."""
        idx = html_content.find('function renderCostTrendChart')
        end = html_content.find('window.renderCostTrendChart', idx)
        block = html_content[idx:end]
        assert 'height="auto"' in block or "height='auto'" in block

    def test_success_chart_svg_height_auto(self, html_content):
        """Success rate chart SVG must have height='auto'."""
        idx = html_content.find('function renderSuccessRateChart')
        end = html_content.find('window.renderSuccessRateChart', idx)
        block = html_content[idx:end]
        assert 'height="auto"' in block or "height='auto'" in block

    def test_charts_section_in_left_panel(self, html_content):
        """charts-section must be within the left panel for layout."""
        left_panel_start = html_content.find('<aside class="left-panel">')
        left_panel_end = html_content.find('</aside>', left_panel_start)
        if left_panel_start < 0:
            # Maybe it uses a different class
            pytest.skip("Left panel not found with expected class")
        charts_section_pos = html_content.find('id="charts-section"')
        assert left_panel_start < charts_section_pos < left_panel_end, \
            "charts-section should be within the left panel"
