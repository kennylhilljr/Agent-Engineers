#!/usr/bin/env python3
"""
Export every issue that matches the JQL in config.yaml.
Creates:
  - CSV file with a flat view (key, summary, status, assignee, created, updated, ...)
  - A sub-folder <output_dir>/<ISSUE_KEY>.json containing the full JSON payload
"""

import csv
import json
import os
from pathlib import Path
from typing import List, Dict, Any

import yaml
from jira import JIRA


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def flatten_issue(issue) -> Dict[str, Any]:
    """Return a flat dict suitable for CSV export."""
    fields = issue.fields
    return {
        "key": issue.key,
        "summary": fields.summary,
        "description": fields.description or "",
        "issue_type": getattr(fields.issuetype, "name", ""),
        "status": getattr(fields.status, "name", ""),
        "assignee": getattr(fields.assignee, "displayName", ""),
        "reporter": getattr(fields.reporter, "displayName", ""),
        "created": fields.created,
        "updated": fields.updated,
        "priority": getattr(fields.priority, "name", ""),
        "labels": ",".join(fields.labels) if hasattr(fields, "labels") else "",
    }


def write_csv(issues: List[Dict[str, Any]], out_path: Path):
    if not issues:
        print("No issues to write.")
        return

    fieldnames = list(issues[0].keys())
    with out_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)
    print(f"CSV written to {out_path}")


def write_json(issue_json: dict, out_path: Path):
    out_path.write_text(
        json.dumps(issue_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main():
    cfg = load_config()
    jira_cfg = cfg["jira"]
    out_cfg = cfg["output"]

    output_dir = Path(out_cfg["directory"])
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialise Jira client
    jira = JIRA(
        server=jira_cfg["server"],
        basic_auth=(jira_cfg["email"], jira_cfg["api_token"]),
    )
    print(f"Authenticated as {jira.current_user()}")

    # Pull issues
    jql = jira_cfg["jql"]
    max_results = jira_cfg.get("max_results")
    print(f"Running JQL: {jql}")
    issues = jira.search_issues(jql, maxResults=max_results, expand="renderedFields")
    print(f"Retrieved {len(issues)} issue(s)")

    # Write CSV + per-issue JSON
    csv_path = output_dir / "kan_issues_export.csv"
    flat_rows = []

    for issue in issues:
        raw_json_path = output_dir / f"{issue.key}.json"
        write_json(issue.raw, raw_json_path)
        flat_rows.append(flatten_issue(issue))

    write_csv(flat_rows, csv_path)

    print(f"\nAll done! Your download package is:")
    print(f"  CSV summary -> {csv_path}")
    print(f"  Individual JSON files -> {output_dir}/*.json")


if __name__ == "__main__":
    main()
