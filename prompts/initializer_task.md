Initialize a new project in: {project_dir}

This is the FIRST session. The project has not been set up yet.

## INITIALIZATION SEQUENCE

### Step 1: Set Up Linear Project
Delegate to `linear` agent:
"Read app_spec.txt to understand what we're building. Then:
1. Create a Linear project with appropriate name
2. Create issues for ALL features from app_spec.txt (with test steps in description)
3. Create a META issue '[META] Project Progress Tracker' for session handoffs
4. Add initial comment to META issue with project summary and session 1 status
5. Save state to .linear_project.json
6. Return: project_id, total_issues created, meta_issue_id"

### Step 2: Initialize Git
Delegate to `github` agent:
"Initialize git repository:
1. git init
2. Create README.md with project overview
3. Create init.sh script to start dev server
4. Initial commit with these files + .linear_project.json"

### Step 3: Start First Feature (if time permits)
Get the highest-priority issue details from linear agent, then delegate to `coding` agent:
"Implement this Linear issue:
- ID: [from linear agent]
- Title: [from linear agent]
- Description: [from linear agent]
- Test Steps: [from linear agent]

Requirements:
1. Implement the feature
2. Test via Playwright (mandatory)
3. Take screenshot evidence
4. Report: files_changed, screenshot_path, test_results"

### Step 4: Commit Progress
If coding was done, delegate to `github` agent to commit.
Then delegate to `linear` agent to add session summary comment to META issue.

## OUTPUT FILES TO CREATE
- .linear_project.json (project state)
- init.sh (dev server startup)
- README.md (project overview)

Remember: You are the orchestrator. Delegate tasks to specialized agents, don't do the work yourself.
