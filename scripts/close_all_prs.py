#!/usr/bin/env python3
"""
Close All Open Pull Requests
=============================

Closes all open pull requests in the configured GitHub repository.

Usage:
    # Using environment variable
    GITHUB_TOKEN=ghp_xxx python scripts/close_all_prs.py

    # Or pass token directly
    python scripts/close_all_prs.py --token ghp_xxx

    # Target a specific repo (default: from GITHUB_REPO env or git remote)
    python scripts/close_all_prs.py --repo owner/repo

    # Dry run (list PRs without closing)
    python scripts/close_all_prs.py --dry-run
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from urllib.error import HTTPError


def get_repo_from_git() -> str | None:
    """Extract owner/repo from git remote origin URL."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        # Handle various URL formats
        for prefix in [
            "https://github.com/",
            "git@github.com:",
            "http://github.com/",
        ]:
            if prefix in url:
                repo = url.split(prefix)[-1]
                return repo.removesuffix(".git").strip("/")
        # Handle proxy URLs like http://proxy@host/git/owner/repo
        if "/git/" in url:
            parts = url.split("/git/")[-1]
            return parts.removesuffix(".git").strip("/")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def github_api(
    method: str, path: str, token: str, data: dict | None = None
) -> dict | list:
    """Make an authenticated GitHub API request."""
    url = f"https://api.github.com{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Authorization", f"token {token}")
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def list_open_prs(owner: str, repo: str, token: str) -> list[dict]:
    """List all open pull requests."""
    prs = []
    page = 1
    while True:
        batch = github_api(
            "GET",
            f"/repos/{owner}/{repo}/pulls?state=open&per_page=100&page={page}",
            token,
        )
        if not batch:
            break
        prs.extend(batch)
        page += 1
    return prs


def close_pr(owner: str, repo: str, pr_number: int, token: str) -> dict:
    """Close a pull request by setting its state to closed."""
    return github_api(
        "PATCH",
        f"/repos/{owner}/{repo}/pulls/{pr_number}",
        token,
        {"state": "closed"},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Close all open pull requests")
    parser.add_argument("--token", help="GitHub personal access token")
    parser.add_argument("--repo", help="Repository in owner/repo format")
    parser.add_argument(
        "--dry-run", action="store_true", help="List PRs without closing"
    )
    args = parser.parse_args()

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GitHub token required. Set GITHUB_TOKEN or use --token")
        sys.exit(1)

    repo_full = args.repo or os.environ.get("GITHUB_REPO") or get_repo_from_git()
    if not repo_full or "/" not in repo_full:
        print("Error: Could not determine repository. Use --repo owner/repo")
        sys.exit(1)

    owner, repo = repo_full.split("/", 1)
    print(f"Repository: {owner}/{repo}")

    try:
        prs = list_open_prs(owner, repo, token)
    except HTTPError as e:
        print(f"Error listing PRs: {e.code} {e.reason}")
        if e.code == 401:
            print("Check your GitHub token.")
        sys.exit(1)

    if not prs:
        print("No open pull requests found.")
        return

    print(f"\nFound {len(prs)} open pull request(s):\n")
    for pr in prs:
        print(f"  #{pr['number']}: {pr['title']}")
        print(f"    Branch: {pr['head']['ref']}")
        print(f"    Author: {pr['user']['login']}")
        print()

    if args.dry_run:
        print("Dry run — no PRs were closed.")
        return

    closed = 0
    failed = 0
    for pr in prs:
        try:
            close_pr(owner, repo, pr["number"], token)
            print(f"  Closed #{pr['number']}: {pr['title']}")
            closed += 1
        except HTTPError as e:
            print(f"  Failed #{pr['number']}: {e.code} {e.reason}")
            failed += 1

    print(f"\nDone: {closed} closed, {failed} failed.")


if __name__ == "__main__":
    main()
