#!/bin/bash
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

# PRs to close with their branch names
declare -A PRS=(
  [186]="project-complete-summary"
  [187]="chore/final-project-completion-session-20"
  [188]="linear_check-check-linear-for-available-tickets"
  [189]="feature/AI-278-dashboard-routing-fix"
  [190]="feature/AI-262-conversation-window-fix"
  [191]="claude/fix-blocked-prs-uS9xq"
)

echo "Closing ${#PRS[@]} stale pull requests in ${REPO}..."
echo

for pr_num in "${!PRS[@]}"; do
  branch="${PRS[$pr_num]}"
  echo "--- PR #${pr_num} (branch: ${branch}) ---"

  # Close the PR
  response=$(curl -s -w "\n%{http_code}" -X PATCH \
    "https://api.github.com/repos/${REPO}/pulls/${pr_num}" \
    -H "${AUTH_HEADER}" \
    -H "Accept: application/vnd.github.v3+json" \
    -H "Content-Type: application/json" \
    -d '{"state": "closed"}')

  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)

  if [ "$http_code" = "200" ]; then
    echo "  Closed PR #${pr_num}"
  else
    echo "  Failed to close PR #${pr_num} (HTTP ${http_code})"
    echo "  $(echo "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("message","unknown error"))' 2>/dev/null || echo "$body")"
    continue
  fi

  # Delete the branch
  response=$(curl -s -w "\n%{http_code}" -X DELETE \
    "https://api.github.com/repos/${REPO}/git/refs/heads/${branch}" \
    -H "${AUTH_HEADER}" \
    -H "Accept: application/vnd.github.v3+json")

  http_code=$(echo "$response" | tail -1)

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
  response=$(curl -s -w "\n%{http_code}" -X DELETE \
    "https://api.github.com/repos/${REPO}/git/refs/heads/${branch}" \
    -H "${AUTH_HEADER}" \
    -H "Accept: application/vnd.github.v3+json")

  http_code=$(echo "$response" | tail -1)

  if [ "$http_code" = "204" ]; then
    echo "  Deleted branch: ${branch}"
  else
    echo "  Failed to delete branch: ${branch} (HTTP ${http_code})"
  fi
done

echo
echo "Cleanup complete!"
