Continue work on the project in: {project_dir}

This is a CONTINUATION session. The project has already been initialized.

## PERFORMANCE RULES (follow these to maximize velocity)

1. **Use `ops` agent for all lightweight operations** — Slack notifications, Linear transitions, and status updates should be batched into a SINGLE `ops` delegation instead of separate linear + slack calls.
2. **Issue parallel delegations** — When two operations are independent (e.g., notify + transition, or review ticket A while coding ticket B), issue them as parallel Task calls.
3. **Conditional verification** — Only run a full Playwright verification test when required (see Step 3).
4. **Assess ticket complexity** — Use `coding_fast` (haiku) for simple changes, `coding` (sonnet) for complex ones. Use `pr_reviewer_fast` for low-risk PRs.
5. **Pipeline tickets** — After submitting a PR for review, start the next ticket immediately without waiting for the review to complete.

---

## STRICT STARTUP SEQUENCE (follow in order)

### Step 1: Orient

- Run `pwd` to confirm working directory
- Read `.linear_project.json` for project IDs (including meta issue ID)

### Step 2: Get Status and Check for Duplicates (CHECK FOR COMPLETION)

Delegate to the `linear` agent:
"Read the project state file, then:

1. Get the latest comment from the META issue for session context
2. List all issues and count by status (Done/In Progress/Todo) - EXCLUDE META issue from counts
3. **DEDUP CHECK:** Group all issues by title (case-insensitive). If any title appears more than once, these are duplicates. Report them and clean them up:
   - Keep the first-created issue (the one with the earliest creation date or lowest key number)
   - Archive the duplicates with a comment: 'Closed as duplicate of [keeper key]'
   - Update the `issues` array in the project state file to remove duplicate keys
   - Adjust `total_issues` count if duplicates were feature issues
4. Compare done count to total_issues from the project state file (after dedup adjustment)
5. Return all_complete: true if done == total_issues, false otherwise
6. If not complete: Get FULL DETAILS of ALL remaining Todo issues (not just one), ordered by priority
7. Return: status counts, all_complete flag, last session context, issues list if not complete, and dedup results (duplicates_found, duplicates_removed)"

**IF all_complete is true:**

1. Delegate to `ops` agent: "Add 'PROJECT COMPLETE' comment to META issue. Send Slack: ':tada: Project complete! All X features implemented and tested.' Create final PR if GITHUB_REPO configured."
2. Output: `PROJECT_COMPLETE: All features implemented and verified.`
3. Session will end.

### Step 3: CONDITIONAL Verification Test

**Check whether to run verification:**
- Read `last_verification_status` and `tickets_since_verification` from `.linear_project.json`
- **SKIP verification if ALL of the following are true:**
  - `last_verification_status` is "pass"
  - `tickets_since_verification` < 3
  - The previous ticket was APPROVED (not CHANGES_REQUESTED)
- **RUN verification if ANY of the following are true:**
  - `last_verification_status` is "fail" or missing
  - `tickets_since_verification` >= 3
  - This is the first ticket of the session
  - The previous ticket had CHANGES_REQUESTED

**If verification RUNS:**
Delegate to `coding` agent:
"Run init.sh to start the dev server, then verify 1-2 completed features still work:

1. Navigate to the app via Playwright
2. Test a core feature end-to-end
3. Take a screenshot as evidence
4. Report: PASS/FAIL with screenshot path

If ANY verification fails, fix it before new work."

After verification:
- Update `.linear_project.json`: set `last_verification_status` to "pass" or "fail"
- If FAIL: delegate to `ops` agent: "Send Slack ':rotating_light: Regression detected — fixing before new work'. Transition issue back to Todo."
  Then ask coding agent to fix the regression. Do NOT proceed until fixed.

**If verification SKIPPED:** Log "Verification skipped (last=pass, tickets_since=N)" and proceed.

### Step 4: Assess Ticket Complexity and Select Agents

For the highest-priority Todo issue from Step 2, assess complexity:

**Simple (use `coding_fast` + `pr_reviewer_fast`):**
- Copy/text changes, CSS/styling fixes
- Config file updates, environment variables
- Adding a test for existing functionality
- README or documentation updates
- Renaming, reorganizing imports

**Complex (use `coding` + `pr_reviewer`):**
- New components or pages
- State management, API routes, database changes
- Authentication, security-related code
- Performance optimization, refactoring
- Integration with external services

### Step 5: Start Ticket — Ops Batch (PARALLEL)

Delegate to `ops` agent (single delegation replaces 2 sequential calls):
"For ticket [KEY] '[TITLE]':
1. Send Slack notification to #ai-cli-macz: ':construction: Starting: [TITLE] ([KEY])'
2. Transition Linear issue [KEY] to In Progress
3. Add comment: 'Work started on this issue.'
Return: confirmation of all operations."

### Step 6: Implement Feature

**REUSE CHECK:** Before delegating to the coding agent, check if the issue description mentions a reusable component (from `reusable/` at the repo root). If so, tell the coding agent to copy and adapt it instead of building from scratch.

Delegate to `coding` or `coding_fast` (based on Step 4 complexity assessment) with FULL context from Step 2:
"Implement this issue:

- Key: [from linear agent]
- Title: [from linear agent]
- Description: [from linear agent]
- Test Steps: [from linear agent]
- Reusable component: [path from reusable/ if mentioned in issue description, otherwise 'none']

Requirements:

1. **If a reusable component is referenced:** Copy it from `reusable/` (one level above the project directory) and adapt it to fit the project. Do NOT rebuild from scratch.
2. Implement the feature (or adapt the reusable component)
3. Write unit/integration tests with robust coverage (REQUIRED)
4. Test via Playwright (browser testing REQUIRED)
5. Take screenshot evidence
6. Report: files_changed, screenshot_path, test_results, test_coverage, reused_component (if any)"

### Step 7: Commit, Push & Create PR (per story)

Delegate to `github` agent:
"Commit and create PR for issue [key]:

- Files changed: [file list from coding agent]
- Issue title: [title]
- Branch: feature/[KEY]-[short-name]
- Push to remote if GITHUB_REPO is configured
- Create PR with issue reference in body
- Return: pr_url, pr_number, branch name"

### Step 8: Move to Review — Ops Batch (PARALLEL)

Delegate to `ops` agent (single delegation replaces 2 sequential calls):
"For ticket [KEY] '[TITLE]':
1. Transition Linear issue [KEY] to Review status
2. Add comment with implementation details:
   - PR URL: [from github agent]
   - Branch name: [from github agent]
   - Files changed: [from coding agent]
   - Test results: [from coding agent]
   - Screenshot evidence: [paths from coding agent]
3. Send Slack notification: ':mag: PR ready for review: [TITLE] ([KEY]) — PR: [url]'
Return: confirmation of all operations."

### Step 9: PR Review (RISK-BASED)

**Assess PR risk level:**

**LOW RISK (auto-approve with `pr_reviewer_fast`):**
- Files changed <= 3
- Only frontend/UI changes (no backend, no API routes, no auth, no database)
- All tests pass
- Changes are additive (new features, not modifying existing logic)

**HIGH RISK (full review with `pr_reviewer`):**
- Backend/API changes
- Auth, security, or database-related files
- Changes touching > 5 files
- Modifying existing shared logic
- Test failures

Delegate to `pr_reviewer` or `pr_reviewer_fast`:
"Review PR for issue:

- Issue Key: [key]
- Title: [issue title]
- PR Number: [number from github agent]
- Files Changed: [list from coding agent]
- Description: [what was implemented]
- Test Steps: [from linear agent]"

The pr_reviewer agent will return one of:
- **APPROVED**: PR passes review — agent merges the PR automatically
- **CHANGES_REQUESTED**: PR needs work — blocking issues listed

### Step 10: Handle Review Outcome

**If APPROVED:**
1. PR is already merged by pr_reviewer agent
2. Delegate to `ops` agent (single delegation replaces 2 sequential calls):
   "For ticket [KEY] '[TITLE]':
   1. Transition Linear issue [KEY] to Done with detailed completion comment:
      - Summary of what was implemented
      - Files changed (ALL files created, modified, or deleted)
      - Test results (commands run, exit codes, coverage)
      - Verification steps (how to confirm this works)
      - Screenshot evidence paths
      - Known limitations (if any)
   2. Send Slack notification: ':white_check_mark: Completed: [TITLE] ([KEY]) — PR merged, Tests: [pass/fail count]'
   Return: confirmation of all operations."
3. Update `.linear_project.json`: increment `tickets_since_verification`

**If CHANGES_REQUESTED:**
1. Delegate to `ops` agent:
   "For ticket [KEY] '[TITLE]':
   1. Move Linear issue [KEY] back to To Do. Add comment listing the blocking issues from the PR review.
   2. Send Slack notification: ':warning: PR changes requested: [TITLE] ([KEY]) — [summary of issues]'
   Return: confirmation."
2. Update `.linear_project.json`: set `last_verification_status` to "fail"
3. Do NOT wait for the next session — pick up this issue (or the next one) immediately in Step 10b below.
4. When re-implementing, pass the blocking issues to the coding agent as additional context.

### Step 10b: Pipeline — Pick Up Next Ticket (CONTINUOUS LOOP)

**After completing Step 10 (whether APPROVED or CHANGES_REQUESTED), do NOT end the session.**
**Instead, loop back and pick up the next ticket immediately:**

1. Delegate to the `linear` agent:
   "List all issues and count by status (Done/In Progress/Todo) - EXCLUDE META issue from counts.
   Check for any duplicate issues (same title, case-insensitive). If found, archive duplicates and update the state file.
   Compare done count to total_issues from the project state file.
   Return: all_complete flag, status counts, dedup results (if any), and FULL DETAILS of the highest-priority Todo issue if not complete."

2. **If all_complete is true:** Go to Project Complete (output `PROJECT_COMPLETE:`).

3. **If there are remaining Todo issues:** Go back to **Step 3** (Conditional Verification) with the new issue and continue the full workflow (Steps 3 → 5 → 6 → 7 → 8 → 9 → 10 → 10b).

**PIPELINE OPTIMIZATION (Proposal 7):** When you have multiple remaining tickets and the coding agent is available, you can start coding the next ticket WHILE the PR reviewer is reviewing the current one. Issue both delegations in parallel:
- `pr_reviewer` reviewing PR for Ticket A
- `coding` implementing Ticket B

When both return, handle the review result for A and continue with B's PR flow.

**Keep looping through tickets until either:**
- All issues are Done (→ trigger PROJECT_COMPLETE)
- Context is critically low and you cannot complete another full ticket cycle

**This is the core work loop. Each session should complete as many tickets as possible, not just one.**

### Step 11: Session End

**11a: If all issues are complete (PROJECT_COMPLETE):**
1. Delegate to `ops` agent: "Add 'PROJECT COMPLETE' comment to META issue. Create final PR if GITHUB_REPO configured. Send Slack: ':tada: Project complete! All X features implemented and tested.'"
2. Output: `PROJECT_COMPLETE: All features implemented and verified.`

**11b: If ending session early (context running low):**
1. Delegate to `ops` agent: "Add session summary comment to META issue with: what was completed, current progress counts, notes for next session. Send Slack: ':memo: Session complete — X issues done, Y remaining'"

## CRITICAL RULES

- Do NOT mark Done without screenshot evidence AND test results from coding agent
- Do NOT start Step 6 if Step 3 verification fails
- Pass FULL issue context to coding agent (don't make it query the tracker)
- Every task MUST have Slack begin + close notifications (via ops agent)
- Coding agent must write tests with robust coverage for every feature
- Every task lifecycle: Started → In Progress → Review → Done (or back to To Do if rejected)
- Use `ops` agent for ALL Linear transitions + Slack notifications (never separate linear + slack calls)
- Use `coding_fast` for simple tickets, `coding` for complex ones
- Use `pr_reviewer_fast` for low-risk PRs, `pr_reviewer` for high-risk

Remember: You are the orchestrator. Delegate tasks to specialized agents, don't do the work yourself.
