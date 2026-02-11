Initialize a new project in: {project_dir}

This is the FIRST session. The project has not been set up yet.

## ISSUE TRACKER DETECTION

Check which issue tracker to use:
- If `JIRA_SERVER` env var is set → use `jira` agent (creates .jira_project.json)
- Otherwise → use `linear` agent (creates .linear_project.json)

## INITIALIZATION SEQUENCE

### Step 1: Set Up Issue Tracking (Jira tickets for EVERY task)

**If using `jira` agent:**
Delegate to `jira` agent:
"Read app_spec.txt to understand what we're building. Then:
1. Verify Jira connection (GET /rest/api/3/myself)
2. Create a Jira issue for EVERY feature/task from app_spec.txt (with test steps in description). Every single task MUST have a corresponding Jira ticket — no exceptions. Use the Jira REST API to actually create each issue.
3. Create a META issue '[META] Project Progress Tracker' for session handoffs
4. Add initial comment to META issue with project summary and session 1 status
5. Save state to .jira_project.json (include every issue key created)
6. Return: project_key, total_issues created, meta_issue_key"

**If using `linear` agent:**
Delegate to `linear` agent:
"Read app_spec.txt to understand what we're building. Then:
1. Create a Linear project with appropriate name
2. Create issues for ALL features/tasks from app_spec.txt (with test steps in description). Every single task MUST have a corresponding issue — no exceptions.
3. Create a META issue '[META] Project Progress Tracker' for session handoffs
4. Add initial comment to META issue with project summary and session 1 status
5. Save state to .linear_project.json
6. Return: project_id, total_issues created, meta_issue_id"

### Step 1b: Slack — Notify Project Created (MANDATORY)

Delegate to `slack` agent:
"Send to #ai-cli-macz: :rocket: Project initialized: [project name] — [total] Jira tickets created"

### Step 2: Initialize Git

Delegate to `github` agent:
"Initialize git repository:
1. git init
2. Create README.md with project overview
3. Create init.sh script to start dev server
4. Initial commit with these files + project state file"

### Step 3: Start First Feature (if time permits)

Get the highest-priority issue details from the issue tracking agent, then:

**Step 3a: Slack — Notify Task Started (MANDATORY)**
Delegate to `slack` agent:
"Send to #ai-cli-macz: :construction: Starting: [issue title] ([issue key])"

**Step 3b: Jira — Transition to In Progress**
Delegate to tracker agent to transition the issue to "In Progress".

**Step 3c: Implement Feature**
Delegate to `coding` agent with FULL context:
"Implement this issue:
- Key: [from tracker agent]
- Title: [from tracker agent]
- Description: [from tracker agent]
- Test Steps: [from tracker agent]

Requirements:
1. Implement the feature
2. Write unit/integration tests with robust coverage (REQUIRED)
3. Test via Playwright (browser testing REQUIRED)
4. Take screenshot evidence
5. Report: files_changed, screenshot_path, test_results, test_coverage"

### Step 4: Commit Progress

If coding was done, delegate to `github` agent to commit.
Then delegate to the tracker agent to mark issue Done and add session summary comment to META issue.

### Step 4b: Slack — Notify Task Completed (MANDATORY)

If a task was completed, delegate to `slack` agent:
"Send to #ai-cli-macz: :white_check_mark: Completed: [issue title] ([issue key]) — Tests: [pass/fail count]"

## OUTPUT FILES TO CREATE

- .jira_project.json or .linear_project.json (project state)
- init.sh (dev server startup)
- README.md (project overview)

## CRITICAL RULES

- Every task gets a Jira ticket — no work without a tracked issue
- Every task gets Slack begin + close notifications — no exceptions
- Coding agent must write tests with robust coverage for every feature
- No shortcuts on test evidence — screenshots + test results required

Remember: You are the orchestrator. Delegate tasks to specialized agents, don't do the work yourself.
