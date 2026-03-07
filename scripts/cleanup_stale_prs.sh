#!/usr/bin/env bash
# Cleanup script to close stale pull requests and delete their branches
#
# Usage: GITHUB_TOKEN=<your-token> ./scripts/cleanup_stale_prs.sh
#
# PRs to close (all analyzed as stale/unnecessary):
#   #186 - PROJECT COMPLETE summary doc (only adds PROJECT_COMPLETION_SUMMARY.md)
#   #187 - Session 20 completion report (stale documentation)
#   #188 - Project Completion Summary (stale documentation, mismatched branch)
#   #189 - AI-278 Dashboard Routing Fix (stale since Feb 22)
#   #190 - AI-262 Conversation Window Fix (has merge conflicts, 72 files)
#   #191 - Refactor conftest.py + CI workflows (stale since Feb 24)

set -euo pipefail

REPO="kennylhilljr/Agent-Engineers"

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "Error: GITHUB_TOKEN environment variable is required"
  echo "Usage: GITHUB_TOKEN=ghp_xxx ./scripts/cleanup_stale_prs.sh"
  exit 1
fi

AUTH_HEADER="Authorization: token ${GITHUB_TOKEN}"

# PRs to close with their branch names (parallel arrays for bash 3 compat)
PR_NUMS=(186 187 188 189 190 191)
PR_BRANCHES=(
  "project-complete-summary"
  "chore/final-project-completion-session-20"
  "linear_check-check-linear-for-available-tickets"
  "feature/AI-278-dashboard-routing-fix"
  "feature/AI-262-conversation-window-fix"
  "claude/fix-blocked-prs-uS9xq"
)

echo "Closing ${#PR_NUMS[@]} stale pull requests in ${REPO}..."
echo

for i in "${!PR_NUMS[@]}"; do
  pr_num="${PR_NUMS[$i]}"
  branch="${PR_BRANCHES[$i]}"
  echo "--- PR #${pr_num} (branch: ${branch}) ---"

  # Close the PR
  http_code=$(curl -s -o /tmp/gh_response.json -w "%{http_code}" -X PATCH \
    "https://api.github.com/repos/${REPO}/pulls/${pr_num}" \
    -H "${AUTH_HEADER}" \
    -H "Accept: application/vnd.github.v3+json" \
    -H "Content-Type: application/json" \
    -d '{"state": "closed"}')

  if [ "$http_code" = "200" ]; then
    echo "  Closed PR #${pr_num}"
  else
    msg=$(python3 -c 'import json; print(json.load(open("/tmp/gh_response.json")).get("message","unknown error"))' 2>/dev/null || echo "HTTP ${http_code}")
    echo "  Failed to close PR #${pr_num} (HTTP ${http_code}): ${msg}"
    continue
  fi

  # Delete the branch
  http_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
    "https://api.github.com/repos/${REPO}/git/refs/heads/${branch}" \
    -H "${AUTH_HEADER}" \
    -H "Accept: application/vnd.github.v3+json")

  if [ "$http_code" = "204" ]; then
    echo "  Deleted branch: ${branch}"
  else
    echo "  Failed to delete branch: ${branch} (HTTP ${http_code})"
  fi

  echo
done

# Also clean up additional stale branches that don't have open PRs
STALE_BRANCHES=(
  "claude/add-qa-agent-HC93f"
  "claude/resolve-pr-conflicts-TBxzG"
  "feature/AI-114-AI-121-qa-improvements"
  "feature/AI-245-team-management-rbac"
  "feature/AI-246-audit-log-compliance"
  "feature/AI-247-ga-pricing-tiers"
  "feature/AI-259-AI-257-AI-258-agent-model-config"
  "feature/AI-260-operations-runbook"
  "feature/AI-263-accelerate-feature"
  "feature/final-cleanup-session-11"
  "final-completion-session-29"
)

echo "=== Cleaning up ${#STALE_BRANCHES[@]} additional stale branches ==="
echo

for branch in "${STALE_BRANCHES[@]}"; do
  http_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
    "https://api.github.com/repos/${REPO}/git/refs/heads/${branch}" \
    -H "${AUTH_HEADER}" \
    -H "Accept: application/vnd.github.v3+json")

  if [ "$http_code" = "204" ]; then
    echo "  Deleted branch: ${branch}"
  else
    echo "  Failed to delete branch: ${branch} (HTTP ${http_code})"
  fi
done

echo
echo "Cleanup complete!"
