#!/usr/bin/env python3
"""
Extract Design Tokens from dashboard.html

Parses the dashboard.html file and extracts all CSS custom properties (variables)
from :root and other CSS blocks, outputting them in a structured JSON format.

Usage:
    python3 scripts/extract_design_tokens.py [--output <path>] [--input <path>]
"""

import re
import json
import sys
import argparse
from pathlib import Path


# Semantic categorization rules based on variable name patterns
CATEGORY_PATTERNS = {
    "colors.background": [
        r"^--bg-",
        r"^--body-bg-",
        r"^--card-bg",
        r"^--header-bg",
        r"^--panel-bg",
        r"^--modal-bg",
        r"^--overlay-bg",
        r"^--sidebar-bg",
        r"^--dropdown-bg",
        r"^--tooltip-bg",
        r"^--input-bg",
    ],
    "colors.text": [
        r"^--text-",
        r"^--label-",
        r"^--heading-",
        r"^--link-",
        r"^--placeholder-",
    ],
    "colors.accent": [
        r"^--accent",
        r"^--primary-",
        r"^--highlight-",
        r"^--focus-",
    ],
    "colors.border": [
        r"^--border-color",
        r"^--border-",
        r"^--divider-",
        r"^--separator-",
    ],
    "colors.status": [
        r"^--success-",
        r"^--error-",
        r"^--warning-",
        r"^--danger-",
        r"^--info-",
        r"^--status-",
        r"^--alert-",
        r"^--color-success",
        r"^--color-error",
        r"^--color-warning",
    ],
    "colors.agent": [
        r"^--agent-",
        r"^--idle-",
        r"^--active-",
        r"^--paused-",
        r"^--stopped-",
    ],
    "typography": [
        r"^--font-",
        r"^--text-size-",
        r"^--line-height-",
        r"^--letter-spacing-",
        r"^--font-weight-",
        r"^--font-size-",
    ],
    "spacing": [
        r"^--spacing-",
        r"^--gap-",
        r"^--padding-",
        r"^--margin-",
        r"^--size-",
    ],
    "borders": [
        r"^--radius-",
        r"^--border-radius-",
        r"^--border-width-",
    ],
    "shadows": [
        r"^--shadow-",
        r"^--box-shadow-",
        r"^--drop-shadow-",
    ],
    "animations": [
        r"^--transition-",
        r"^--animation-",
        r"^--duration-",
        r"^--easing-",
        r"^--timing-",
    ],
    "layout": [
        r"^--width-",
        r"^--height-",
        r"^--max-width-",
        r"^--min-width-",
        r"^--z-index-",
        r"^--panel-width",
        r"^--sidebar-width",
        r"^--header-height",
    ],
    "components.progress": [
        r"^--progress-",
    ],
    "components.badge": [
        r"^--badge-",
    ],
    "components.card": [
        r"^--card-",
    ],
    "components.button": [
        r"^--btn-",
        r"^--button-",
    ],
    "components.chart": [
        r"^--chart-",
    ],
    "other": [],
}


def categorize_variable(name: str) -> str:
    """Determine semantic category for a CSS variable name."""
    for category, patterns in CATEGORY_PATTERNS.items():
        if category == "other":
            continue
        for pattern in patterns:
            if re.match(pattern, name):
                return category
    return "other"


def extract_root_block(content: str) -> dict[str, str]:
    """Extract CSS variables from the :root block."""
    root_vars = {}
    # Match :root { ... } blocks (possibly multiple)
    root_blocks = re.findall(r':root\s*\{([^}]+)\}', content, re.DOTALL)
    for block in root_blocks:
        matches = re.findall(r'(--[a-zA-Z0-9-]+)\s*:\s*([^;]+);', block)
        for name, value in matches:
            if name not in root_vars:
                root_vars[name] = value.strip()
    return root_vars


def extract_theme_overrides(content: str) -> dict[str, dict[str, str]]:
    """Extract theme-specific overrides (e.g., [data-theme='light'])."""
    themes = {}
    # Match [data-theme="xxx"] { ... } blocks
    theme_blocks = re.findall(
        r'\[data-theme=["\']([^"\']+)["\']\]\s*\{([^}]+)\}', content, re.DOTALL
    )
    for theme_name, block in theme_blocks:
        theme_vars = {}
        matches = re.findall(r'(--[a-zA-Z0-9-]+)\s*:\s*([^;]+);', block)
        for name, value in matches:
            theme_vars[name] = value.strip()
        themes[theme_name] = theme_vars
    return themes


def extract_all_variables(content: str) -> dict[str, str]:
    """Extract ALL CSS variable definitions from the entire file."""
    all_vars = {}
    matches = re.findall(r'(--[a-zA-Z0-9-]+)\s*:\s*([^;}{]+);', content)
    for name, value in matches:
        value = value.strip()
        if value and name not in all_vars:
            all_vars[name] = value
    return all_vars


def extract_usages(content: str) -> dict[str, int]:
    """Count how many times each CSS variable is referenced via var(--name)."""
    usages = {}
    refs = re.findall(r'var\((--[a-zA-Z0-9-]+)', content)
    for ref in refs:
        usages[ref] = usages.get(ref, 0) + 1
    return usages


def extract_hardcoded_colors(content: str) -> list[str]:
    """Find hardcoded hex color values not using CSS variables."""
    # Only look in CSS sections (between <style> tags)
    css_sections = re.findall(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
    css_content = '\n'.join(css_sections)
    # Find hex colors that are NOT in var() expressions or definitions
    colors = set()
    # Simple hex colors: #rgb or #rrggbb
    hex_colors = re.findall(r'(?<![a-zA-Z0-9-])#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b', css_content)
    for c in hex_colors:
        colors.add('#' + c)
    return list(colors)


def organize_tokens(
    root_vars: dict[str, str],
    all_vars: dict[str, str],
    usages: dict[str, int],
    themes: dict[str, dict[str, str]],
    hardcoded_colors: list[str],
) -> dict:
    """Organize extracted tokens into the final structured output."""
    # Categorize all variables
    categorized: dict[str, dict[str, dict]] = {}
    for category in CATEGORY_PATTERNS:
        categorized[category] = {}

    for name, value in all_vars.items():
        category = categorize_variable(name)
        categorized[category][name] = {
            "value": value,
            "is_root": name in root_vars,
            "usage_count": usages.get(name, 0),
        }

    # Remove empty categories
    categorized = {k: v for k, v in categorized.items() if v}

    return {
        "metadata": {
            "source": "dashboard/dashboard.html",
            "total_variables": len(all_vars),
            "root_variables": len(root_vars),
            "total_usages": sum(usages.values()),
            "themes": list(themes.keys()),
            "hardcoded_color_count": len(hardcoded_colors),
        },
        "root": root_vars,
        "themes": themes,
        "categories": categorized,
        "hardcoded_colors": hardcoded_colors,
        "usage_stats": usages,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract CSS design tokens from dashboard.html")
    parser.add_argument(
        "--input",
        default="dashboard/dashboard.html",
        help="Path to input HTML file (default: dashboard/dashboard.html)",
    )
    parser.add_argument(
        "--output",
        default="design_tokens.json",
        help="Path to output JSON file (default: design_tokens.json)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print output to stdout instead of writing to file",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    content = input_path.read_text(encoding="utf-8")

    print(f"Analyzing: {input_path} ({len(content):,} bytes, {content.count(chr(10)):,} lines)")

    root_vars = extract_root_block(content)
    print(f"Found {len(root_vars)} :root CSS variables")

    themes = extract_theme_overrides(content)
    print(f"Found {len(themes)} theme overrides: {list(themes.keys())}")

    all_vars = extract_all_variables(content)
    print(f"Found {len(all_vars)} total CSS variable definitions")

    usages = extract_usages(content)
    print(f"Found {sum(usages.values())} total CSS variable usages ({len(usages)} unique)")

    hardcoded_colors = extract_hardcoded_colors(content)
    print(f"Found {len(hardcoded_colors)} hardcoded color values")

    tokens = organize_tokens(root_vars, all_vars, usages, themes, hardcoded_colors)

    output_json = json.dumps(tokens, indent=2)

    if args.stdout:
        print(output_json)
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        print(f"Design tokens written to: {output_path}")

    # Print summary by category
    print("\nTokens by category:")
    for category, vars_dict in tokens["categories"].items():
        print(f"  {category}: {len(vars_dict)} variables")

    return tokens


if __name__ == "__main__":
    main()
