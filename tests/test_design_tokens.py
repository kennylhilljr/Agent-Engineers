"""
Tests for design tokens extraction and validation (AI-241).

Verifies:
- design_tokens.json is valid and parseable
- Required token categories exist
- CSS extraction script works correctly
- Token values are valid CSS
- Design system documentation exists
"""

import json
import re
import sys
from pathlib import Path

import pytest

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DESIGN_TOKENS_PATH = PROJECT_ROOT / "design_tokens.json"
DASHBOARD_HTML_PATH = PROJECT_ROOT / "dashboard" / "dashboard.html"
EXTRACT_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "extract_design_tokens.py"
DESIGN_SYSTEM_DOC_PATH = PROJECT_ROOT / "docs" / "DESIGN_SYSTEM.md"
A2UI_PLAN_DOC_PATH = PROJECT_ROOT / "docs" / "A2UI_INTEGRATION_PLAN.md"
DESIGNS_DIR = PROJECT_ROOT / "docs" / "designs"


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tokens() -> dict:
    """Load design_tokens.json once for all tests."""
    assert DESIGN_TOKENS_PATH.exists(), (
        f"design_tokens.json not found at {DESIGN_TOKENS_PATH}. "
        "Run: python3 scripts/extract_design_tokens.py"
    )
    with DESIGN_TOKENS_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def dashboard_content() -> str:
    """Load dashboard.html content once for all tests."""
    assert DASHBOARD_HTML_PATH.exists(), f"dashboard.html not found at {DASHBOARD_HTML_PATH}"
    return DASHBOARD_HTML_PATH.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# Test 1: design_tokens.json is valid JSON
# ─────────────────────────────────────────────────────────────

def test_design_tokens_file_exists():
    """design_tokens.json must exist in project root."""
    assert DESIGN_TOKENS_PATH.exists(), (
        f"design_tokens.json not found at {DESIGN_TOKENS_PATH}"
    )


def test_design_tokens_is_valid_json():
    """design_tokens.json must be parseable as valid JSON."""
    content = DESIGN_TOKENS_PATH.read_text(encoding="utf-8")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        pytest.fail(f"design_tokens.json is not valid JSON: {e}")
    assert isinstance(data, dict), "design_tokens.json must be a JSON object (dict)"


# ─────────────────────────────────────────────────────────────
# Test 2: Required top-level keys exist
# ─────────────────────────────────────────────────────────────

def test_design_tokens_has_required_top_level_keys(tokens: dict):
    """design_tokens.json must have all required top-level keys."""
    required_keys = {"metadata", "root", "themes", "categories", "hardcoded_colors", "usage_stats"}
    missing = required_keys - set(tokens.keys())
    assert not missing, f"design_tokens.json missing keys: {missing}"


# ─────────────────────────────────────────────────────────────
# Test 3: Metadata structure is correct
# ─────────────────────────────────────────────────────────────

def test_design_tokens_metadata_structure(tokens: dict):
    """Metadata section must have all expected fields."""
    meta = tokens["metadata"]
    required_meta_keys = {
        "source", "total_variables", "root_variables",
        "total_usages", "themes", "hardcoded_color_count",
    }
    missing = required_meta_keys - set(meta.keys())
    assert not missing, f"metadata missing keys: {missing}"


def test_design_tokens_metadata_values_are_positive(tokens: dict):
    """Metadata numeric values must be positive integers."""
    meta = tokens["metadata"]
    assert meta["total_variables"] > 0, "total_variables must be > 0"
    assert meta["root_variables"] > 0, "root_variables must be > 0"
    assert meta["total_usages"] > 0, "total_usages must be > 0"
    assert meta["hardcoded_color_count"] >= 0, "hardcoded_color_count must be >= 0"


# ─────────────────────────────────────────────────────────────
# Test 4: Root CSS variables are present
# ─────────────────────────────────────────────────────────────

def test_design_tokens_root_variables_exist(tokens: dict):
    """Root CSS variables section must contain variables."""
    root = tokens["root"]
    assert isinstance(root, dict), "root must be a dict"
    assert len(root) > 0, "root must contain at least one variable"


def test_design_tokens_required_root_variables(tokens: dict):
    """Core CSS variables must be present in root."""
    root = tokens["root"]
    required_vars = {
        "--bg-primary",
        "--bg-secondary",
        "--text-primary",
        "--text-secondary",
        "--border-color",
        "--accent",
    }
    missing = required_vars - set(root.keys())
    assert not missing, f"Required root CSS variables missing: {missing}"


# ─────────────────────────────────────────────────────────────
# Test 5: Required token categories exist
# ─────────────────────────────────────────────────────────────

def test_design_tokens_has_categories(tokens: dict):
    """Categories section must exist and be non-empty."""
    categories = tokens["categories"]
    assert isinstance(categories, dict), "categories must be a dict"
    assert len(categories) > 0, "categories must be non-empty"


def test_design_tokens_required_categories_present(tokens: dict):
    """Essential token categories must be present."""
    categories = tokens["categories"]
    required_categories = {
        "colors.background",
        "colors.text",
        "colors.accent",
        "colors.border",
    }
    missing = required_categories - set(categories.keys())
    assert not missing, f"Required token categories missing: {missing}"


# ─────────────────────────────────────────────────────────────
# Test 6: Theme overrides exist
# ─────────────────────────────────────────────────────────────

def test_design_tokens_has_light_theme(tokens: dict):
    """Light theme override must be present."""
    themes = tokens["themes"]
    assert "light" in themes, "Light theme override must exist in themes"
    light_theme = themes["light"]
    assert len(light_theme) > 0, "Light theme must have at least one variable override"


def test_design_tokens_light_theme_overrides_core_vars(tokens: dict):
    """Light theme must override the core CSS variables."""
    light_theme = tokens["themes"]["light"]
    core_overrides = {"--bg-primary", "--text-primary", "--accent", "--border-color"}
    missing = core_overrides - set(light_theme.keys())
    assert not missing, f"Light theme missing core overrides: {missing}"


# ─────────────────────────────────────────────────────────────
# Test 7: Category entries have valid structure
# ─────────────────────────────────────────────────────────────

def test_design_tokens_category_entries_have_correct_shape(tokens: dict):
    """Each token entry in categories must have 'value', 'is_root', 'usage_count'."""
    categories = tokens["categories"]
    for category_name, variables in categories.items():
        for var_name, var_data in variables.items():
            assert "value" in var_data, (
                f"Variable {var_name} in {category_name} missing 'value'"
            )
            assert "is_root" in var_data, (
                f"Variable {var_name} in {category_name} missing 'is_root'"
            )
            assert "usage_count" in var_data, (
                f"Variable {var_name} in {category_name} missing 'usage_count'"
            )
            assert isinstance(var_data["usage_count"], int), (
                f"usage_count for {var_name} must be an int"
            )
            assert var_data["usage_count"] >= 0, (
                f"usage_count for {var_name} must be non-negative"
            )


# ─────────────────────────────────────────────────────────────
# Test 8: Hardcoded colors list is non-empty
# ─────────────────────────────────────────────────────────────

def test_design_tokens_hardcoded_colors_list(tokens: dict):
    """Hardcoded colors must be a non-empty list (dashboard.html has many)."""
    hardcoded = tokens["hardcoded_colors"]
    assert isinstance(hardcoded, list), "hardcoded_colors must be a list"
    # The dashboard has many hardcoded colors — we know there are at least 20
    assert len(hardcoded) >= 20, (
        f"Expected at least 20 hardcoded colors, got {len(hardcoded)}. "
        "This may indicate a parsing issue."
    )


def test_design_tokens_hardcoded_colors_are_hex(tokens: dict):
    """All hardcoded color values should look like hex colors."""
    hardcoded = tokens["hardcoded_colors"]
    hex_pattern = re.compile(r'^#[0-9a-fA-F]{3,8}$')
    for color in hardcoded:
        assert hex_pattern.match(color), (
            f"Hardcoded color '{color}' does not look like a hex color"
        )


# ─────────────────────────────────────────────────────────────
# Test 9: Usage stats are consistent
# ─────────────────────────────────────────────────────────────

def test_design_tokens_usage_stats_exist(tokens: dict):
    """Usage stats must exist and contain variable references."""
    usage = tokens["usage_stats"]
    assert isinstance(usage, dict), "usage_stats must be a dict"
    assert len(usage) > 0, "usage_stats must be non-empty"


def test_design_tokens_usage_stats_match_root_vars(tokens: dict):
    """All root variables should appear in usage stats (they are used in dashboard.html)."""
    root_vars = set(tokens["root"].keys())
    usage_vars = set(tokens["usage_stats"].keys())
    # Not all root vars must be in usage stats (could have orphaned vars)
    # but at least some root vars should appear in usage stats
    intersection = root_vars & usage_vars
    assert len(intersection) > 0, (
        "No root CSS variables appear in usage stats — something is wrong"
    )


# ─────────────────────────────────────────────────────────────
# Test 10: CSS extraction script exists and is importable
# ─────────────────────────────────────────────────────────────

def test_extract_script_exists():
    """The CSS token extraction script must exist."""
    assert EXTRACT_SCRIPT_PATH.exists(), (
        f"Token extraction script not found at {EXTRACT_SCRIPT_PATH}"
    )


def test_extract_script_is_valid_python():
    """The extraction script must be syntactically valid Python."""
    source = EXTRACT_SCRIPT_PATH.read_text(encoding="utf-8")
    try:
        compile(source, str(EXTRACT_SCRIPT_PATH), "exec")
    except SyntaxError as e:
        pytest.fail(f"extract_design_tokens.py has syntax error: {e}")


def test_extract_script_has_required_functions():
    """The extraction script must define required functions."""
    source = EXTRACT_SCRIPT_PATH.read_text(encoding="utf-8")
    required_functions = [
        "extract_root_block",
        "extract_theme_overrides",
        "extract_all_variables",
        "extract_usages",
        "organize_tokens",
        "main",
    ]
    for func_name in required_functions:
        assert f"def {func_name}" in source, (
            f"Function '{func_name}' not found in extract_design_tokens.py"
        )


# ─────────────────────────────────────────────────────────────
# Test 11: CSS extraction functions work correctly
# ─────────────────────────────────────────────────────────────

def test_extract_root_block_function():
    """extract_root_block should correctly parse a :root block."""
    # Import the module dynamically
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "extract_design_tokens", EXTRACT_SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Test with a known CSS snippet
    test_css = """
    :root {
        --bg-primary: #0d1117;
        --text-primary: #e6edf3;
        --accent: #58a6ff;
    }
    """
    result = module.extract_root_block(test_css)
    assert result.get("--bg-primary") == "#0d1117"
    assert result.get("--text-primary") == "#e6edf3"
    assert result.get("--accent") == "#58a6ff"
    assert len(result) == 3


def test_extract_theme_overrides_function():
    """extract_theme_overrides should correctly parse theme overrides."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "extract_design_tokens", EXTRACT_SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    test_css = """
    [data-theme="light"] {
        --bg-primary: #ffffff;
        --accent: #0969da;
    }
    """
    result = module.extract_theme_overrides(test_css)
    assert "light" in result
    assert result["light"]["--bg-primary"] == "#ffffff"
    assert result["light"]["--accent"] == "#0969da"


def test_extract_usages_function():
    """extract_usages should count variable references correctly."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "extract_design_tokens", EXTRACT_SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    test_css = """
    .foo { color: var(--text-primary); }
    .bar { color: var(--text-primary); background: var(--bg-secondary); }
    .baz { border: 1px solid var(--border-color); }
    """
    result = module.extract_usages(test_css)
    assert result.get("--text-primary") == 2
    assert result.get("--bg-secondary") == 1
    assert result.get("--border-color") == 1


# ─────────────────────────────────────────────────────────────
# Test 12: Extraction script works on actual dashboard.html
# ─────────────────────────────────────────────────────────────

def test_extract_script_on_real_dashboard(dashboard_content: str):
    """The extraction script must successfully parse the real dashboard.html."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "extract_design_tokens", EXTRACT_SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    root_vars = module.extract_root_block(dashboard_content)
    assert len(root_vars) > 0, "No root variables found in dashboard.html"
    assert "--bg-primary" in root_vars, "--bg-primary not found in dashboard.html :root"
    assert "--text-primary" in root_vars, "--text-primary not found in dashboard.html :root"

    usages = module.extract_usages(dashboard_content)
    assert sum(usages.values()) > 100, (
        f"Expected >100 CSS variable usages, got {sum(usages.values())}"
    )


# ─────────────────────────────────────────────────────────────
# Test 13: Documentation files exist
# ─────────────────────────────────────────────────────────────

def test_design_system_doc_exists():
    """docs/DESIGN_SYSTEM.md must exist."""
    assert DESIGN_SYSTEM_DOC_PATH.exists(), (
        f"DESIGN_SYSTEM.md not found at {DESIGN_SYSTEM_DOC_PATH}"
    )


def test_design_system_doc_has_required_sections():
    """DESIGN_SYSTEM.md must contain required section headings."""
    content = DESIGN_SYSTEM_DOC_PATH.read_text(encoding="utf-8")
    required_sections = [
        "Design Tokens",
        "Color Palette",
        "Typography",
        "Spacing",
        "Component Inventory",
        "Animation",
    ]
    for section in required_sections:
        assert section in content, (
            f"Section '{section}' not found in DESIGN_SYSTEM.md"
        )


def test_a2ui_integration_plan_exists():
    """docs/A2UI_INTEGRATION_PLAN.md must exist."""
    assert A2UI_PLAN_DOC_PATH.exists(), (
        f"A2UI_INTEGRATION_PLAN.md not found at {A2UI_PLAN_DOC_PATH}"
    )


def test_a2ui_integration_plan_has_required_sections():
    """A2UI_INTEGRATION_PLAN.md must contain required section headings."""
    content = A2UI_PLAN_DOC_PATH.read_text(encoding="utf-8")
    required_sections = [
        "A2UI Component Inventory",
        "Compatibility Assessment",
        "Migration Strategy",
        "Phase Plan",
        "Effort Estimates",
    ]
    for section in required_sections:
        assert section in content, (
            f"Section '{section}' not found in A2UI_INTEGRATION_PLAN.md"
        )


# ─────────────────────────────────────────────────────────────
# Test 14: Design spec files exist
# ─────────────────────────────────────────────────────────────

def test_design_specs_directory_exists():
    """docs/designs/ directory must exist."""
    assert DESIGNS_DIR.exists() and DESIGNS_DIR.is_dir(), (
        f"docs/designs/ directory not found at {DESIGNS_DIR}"
    )


@pytest.mark.parametrize("spec_file", [
    "ONBOARDING_WIZARD.md",
    "BILLING_PAGE.md",
    "SETTINGS_PROFILE.md",
    "ANALYTICS_DASHBOARD.md",
])
def test_design_spec_file_exists(spec_file: str):
    """Each required Phase 2 design spec file must exist."""
    spec_path = DESIGNS_DIR / spec_file
    assert spec_path.exists(), f"Design spec not found: {spec_path}"


@pytest.mark.parametrize("spec_file", [
    "ONBOARDING_WIZARD.md",
    "BILLING_PAGE.md",
    "SETTINGS_PROFILE.md",
    "ANALYTICS_DASHBOARD.md",
])
def test_design_spec_has_required_sections(spec_file: str):
    """Each design spec must contain standard required sections."""
    spec_path = DESIGNS_DIR / spec_file
    content = spec_path.read_text(encoding="utf-8")
    required_sections = [
        "## Overview",
        "## Layout",
        "## Component List",
        "## User Flow",
        "## Key Interactions",
    ]
    for section in required_sections:
        assert section in content, (
            f"Section '{section}' not found in {spec_file}"
        )


# ─────────────────────────────────────────────────────────────
# Test 15: Designer agent prompt references design system
# ─────────────────────────────────────────────────────────────

def test_designer_agent_prompt_exists():
    """prompts/designer_agent_prompt.md must exist."""
    prompt_path = PROJECT_ROOT / "prompts" / "designer_agent_prompt.md"
    assert prompt_path.exists(), f"Designer agent prompt not found at {prompt_path}"


def test_designer_agent_prompt_references_design_system():
    """Designer agent prompt must reference the design system docs."""
    prompt_path = PROJECT_ROOT / "prompts" / "designer_agent_prompt.md"
    content = prompt_path.read_text(encoding="utf-8")
    # Must mention the key design system artifacts
    required_references = [
        "DESIGN_SYSTEM.md",
        "design_tokens.json",
        "A2UI_INTEGRATION_PLAN.md",
        "docs/designs/",
    ]
    for ref in required_references:
        assert ref in content, (
            f"Designer agent prompt must reference '{ref}'"
        )


def test_designer_agent_prompt_has_figma_instructions():
    """Designer agent prompt must include Figma integration instructions."""
    prompt_path = PROJECT_ROOT / "prompts" / "designer_agent_prompt.md"
    content = prompt_path.read_text(encoding="utf-8")
    assert "Figma" in content, "Designer agent prompt must mention Figma"
    assert "Figma MCP" in content or "Figma integration" in content.lower(), (
        "Designer agent prompt must include Figma MCP integration instructions"
    )


# ─────────────────────────────────────────────────────────────
# Test 16: Token categorization is correct
# ─────────────────────────────────────────────────────────────

def test_categorize_variable_function():
    """categorize_variable must correctly categorize variable names."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "extract_design_tokens", EXTRACT_SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Test known categorizations
    assert module.categorize_variable("--bg-primary") == "colors.background"
    assert module.categorize_variable("--bg-secondary") == "colors.background"
    assert module.categorize_variable("--text-primary") == "colors.text"
    assert module.categorize_variable("--text-secondary") == "colors.text"
    assert module.categorize_variable("--accent") == "colors.accent"
    assert module.categorize_variable("--border-color") == "colors.border"
    assert module.categorize_variable("--transition-theme") == "animations"
    assert module.categorize_variable("--shadow-card") == "shadows"
    assert module.categorize_variable("--font-size-lg") == "typography"
    assert module.categorize_variable("--spacing-4") == "spacing"
    assert module.categorize_variable("--radius-md") == "borders"
    # Unknown should fall back to "other"
    assert module.categorize_variable("--totally-unknown-var") == "other"


# ─────────────────────────────────────────────────────────────
# Test 17: Root variables have valid CSS values
# ─────────────────────────────────────────────────────────────

def test_root_variable_values_are_non_empty(tokens: dict):
    """All root CSS variable values must be non-empty strings."""
    root = tokens["root"]
    for var_name, value in root.items():
        assert isinstance(value, str), f"Value for {var_name} must be a string"
        assert len(value.strip()) > 0, f"Value for {var_name} must not be empty"


def test_root_color_variables_have_valid_formats(tokens: dict):
    """Root color variables must have values in valid CSS color formats."""
    root = tokens["root"]
    color_vars = ["--bg-primary", "--bg-secondary", "--text-primary",
                  "--text-secondary", "--border-color", "--accent"]
    # Valid CSS color formats: hex, rgb(), rgba(), hsl(), named
    color_pattern = re.compile(
        r'^(#[0-9a-fA-F]{3,8}|rgb\(|rgba\(|hsl\(|hsla\(|[a-z]+).*',
        re.IGNORECASE
    )
    for var in color_vars:
        value = root.get(var, "")
        assert color_pattern.match(value), (
            f"Variable {var} value '{value}' doesn't look like a valid CSS color"
        )


# ─────────────────────────────────────────────────────────────
# Test 18: Dashboard.html has CSS variables in use
# ─────────────────────────────────────────────────────────────

def test_dashboard_uses_css_variables(dashboard_content: str):
    """dashboard.html must use CSS custom properties via var()."""
    var_usages = re.findall(r'var\(--[a-zA-Z0-9-]+', dashboard_content)
    assert len(var_usages) > 50, (
        f"Expected >50 CSS variable usages in dashboard.html, found {len(var_usages)}"
    )


def test_dashboard_has_root_block(dashboard_content: str):
    """dashboard.html must have a :root CSS block with custom properties."""
    assert ":root" in dashboard_content, "dashboard.html must contain a :root CSS block"
    root_blocks = re.findall(r':root\s*\{([^}]+)\}', dashboard_content, re.DOTALL)
    assert len(root_blocks) > 0, "No :root blocks found in dashboard.html CSS"
    combined = "\n".join(root_blocks)
    css_vars = re.findall(r'--[a-zA-Z0-9-]+\s*:', combined)
    assert len(css_vars) > 5, (
        f"Expected >5 CSS variables in :root, found {len(css_vars)}"
    )


def test_dashboard_has_light_theme(dashboard_content: str):
    """dashboard.html must have a light theme override block."""
    assert '[data-theme=' in dashboard_content or "data-theme" in dashboard_content, (
        "dashboard.html must have data-theme attribute support"
    )
    light_block = re.search(r'\[data-theme=["\']light["\']\]', dashboard_content)
    assert light_block, "dashboard.html must have a [data-theme='light'] CSS block"
