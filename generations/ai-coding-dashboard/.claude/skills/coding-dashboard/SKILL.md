# AI Coding Dashboard Integration Skill

This skill enables external AI agents (like Claude Code) to integrate with the AI Coding Dashboard by pushing development events and receiving human approvals/decisions via REST API.

## Overview

The AI Coding Dashboard provides a real-time interface for monitoring AI agent activity, tracking development progress, and enabling human-in-the-loop decision-making. External agents can push events to the dashboard and poll for human responses.

**Base URL**: `http://localhost:8000`

**Documentation**: Available at `http://localhost:8000/docs` (OpenAPI/Swagger)

---

## Quick Start

### 1. Start the Dashboard Backend

```bash
cd /path/to/ai-coding-dashboard/agent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The backend will start on `http://localhost:8000`.

### 2. Create a Project

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-claude-project",
    "name": "My AI Development Project",
    "description": "Project managed by Claude Code agent"
  }'
```

**Response**:
```json
{
  "project_id": "my-claude-project",
  "name": "My AI Development Project",
  "description": "Project managed by Claude Code agent",
  "tasks": [],
  "created_at": "2026-02-11T10:00:00Z",
  "updated_at": "2026-02-11T10:00:00Z"
}
```

### 3. Push Events to Dashboard

Send events as your agent performs work:

```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-claude-project",
    "event_type": "task_started",
    "data": {
      "task_id": "TASK-001",
      "description": "Implement user authentication"
    }
  }'
```

---

## API Endpoints

### Projects API

#### Create Project

**POST** `/api/projects`

Create a new project for tracking AI agent activity.

**Request Body**:
```json
{
  "project_id": "unique-project-id",
  "name": "Project Name",
  "description": "Optional project description"
}
```

**Response**: `201 Created`
```json
{
  "project_id": "unique-project-id",
  "name": "Project Name",
  "description": "Optional project description",
  "tasks": [],
  "created_at": "2026-02-11T10:00:00Z",
  "updated_at": "2026-02-11T10:00:00Z"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "claude-refactor-2024",
    "name": "Code Refactoring Initiative",
    "description": "Automated refactoring by Claude Code"
  }'
```

#### Get Project

**GET** `/api/projects/{project_id}`

Retrieve project details and current state.

**Response**: `200 OK`
```json
{
  "project_id": "claude-refactor-2024",
  "name": "Code Refactoring Initiative",
  "description": "Automated refactoring by Claude Code",
  "tasks": [
    {
      "id": "TASK-001",
      "description": "Refactor authentication module",
      "status": "in_progress",
      "category": "refactoring",
      "priority": 1,
      "created_at": "2026-02-11T10:00:00Z",
      "updated_at": "2026-02-11T10:05:00Z"
    }
  ],
  "created_at": "2026-02-11T10:00:00Z",
  "updated_at": "2026-02-11T10:05:00Z"
}
```

**Example**:
```bash
curl http://localhost:8000/api/projects/claude-refactor-2024
```

---

### Events API

#### Push Event

**POST** `/api/events`

Send an event to the dashboard to track agent activity.

**Request Body**:
```json
{
  "project_id": "project-id",
  "event_type": "event_type",
  "data": {
    "key": "value"
  },
  "timestamp": "2026-02-11T10:00:00Z"
}
```

**Event Types**: See [Event Types](#event-types) section below.

**Response**: `202 Accepted`
```json
{
  "status": "accepted",
  "event_id": "evt_abc123",
  "timestamp": "2026-02-11T10:00:00Z"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "claude-refactor-2024",
    "event_type": "task_completed",
    "data": {
      "task_id": "TASK-001",
      "description": "Refactored authentication module",
      "files_changed": ["src/auth/login.ts", "src/auth/session.ts"],
      "tests_passed": true
    }
  }'
```

---

## Event Types

### 1. task_started

Indicates the agent has started working on a task.

**Data Schema**:
```json
{
  "task_id": "TASK-001",
  "description": "Task description",
  "category": "feature|bug|enhancement|refactoring|testing|documentation",
  "priority": 1
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-project",
    "event_type": "task_started",
    "data": {
      "task_id": "TASK-002",
      "description": "Add input validation",
      "category": "enhancement",
      "priority": 2
    }
  }'
```

---

### 2. task_completed

Indicates the agent has completed a task.

**Data Schema**:
```json
{
  "task_id": "TASK-001",
  "description": "Task description",
  "files_changed": ["file1.ts", "file2.ts"],
  "tests_passed": true,
  "test_coverage": 85.5,
  "screenshot_evidence": ["screenshots/feature-working.png"]
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-project",
    "event_type": "task_completed",
    "data": {
      "task_id": "TASK-002",
      "description": "Added input validation",
      "files_changed": ["src/components/Form.tsx", "src/utils/validate.ts"],
      "tests_passed": true,
      "test_coverage": 92.3,
      "screenshot_evidence": ["screenshots/TASK-002-validation.png"]
    }
  }'
```

---

### 3. decision_needed

Request human input for a decision.

**Data Schema**:
```json
{
  "decision_id": "DEC-001",
  "question": "Should I proceed with breaking change?",
  "options": ["yes", "no", "skip"],
  "context": "Updating API will break 3 existing endpoints",
  "timeout_seconds": 300
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-project",
    "event_type": "decision_needed",
    "data": {
      "decision_id": "DEC-001",
      "question": "Should I proceed with refactoring the entire authentication system?",
      "options": ["yes", "no", "pause_for_review"],
      "context": "This will affect 15 files and require updating tests",
      "timeout_seconds": 600
    }
  }'
```

To get the response:
```bash
curl http://localhost:8000/api/responses/DEC-001
```

---

### 4. approval_needed

Request approval before executing an action.

**Data Schema**:
```json
{
  "approval_id": "APR-001",
  "action": "delete_files",
  "details": {
    "files": ["old-config.json", "deprecated.ts"],
    "reason": "Files no longer needed after migration"
  },
  "risk_level": "medium"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-project",
    "event_type": "approval_needed",
    "data": {
      "approval_id": "APR-001",
      "action": "deploy_to_production",
      "details": {
        "environment": "production",
        "changes": "Updated authentication flow",
        "affected_users": "all"
      },
      "risk_level": "high"
    }
  }'
```

To get the approval response:
```bash
curl http://localhost:8000/api/responses/APR-001
```

---

### 5. error

Report an error encountered by the agent.

**Data Schema**:
```json
{
  "error_id": "ERR-001",
  "error_type": "compilation_error|test_failure|runtime_error|api_error",
  "message": "Error message",
  "stack_trace": "Optional stack trace",
  "file": "Optional file path",
  "line": 42
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-project",
    "event_type": "error",
    "data": {
      "error_id": "ERR-001",
      "error_type": "test_failure",
      "message": "3 tests failed after refactoring",
      "file": "src/auth/__tests__/login.test.ts",
      "details": {
        "failed_tests": ["should login user", "should handle invalid credentials", "should refresh token"]
      }
    }
  }'
```

---

### 6. milestone

Report reaching a significant milestone.

**Data Schema**:
```json
{
  "milestone_id": "MILE-001",
  "title": "Milestone title",
  "description": "Milestone description",
  "percentage": 50
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-project",
    "event_type": "milestone",
    "data": {
      "milestone_id": "MILE-001",
      "title": "50% Complete",
      "description": "Completed authentication refactoring and testing",
      "percentage": 50,
      "tasks_completed": 5,
      "tasks_remaining": 5
    }
  }'
```

---

### 7. file_changed

Report file modifications made by the agent.

**Data Schema**:
```json
{
  "file_path": "src/components/Button.tsx",
  "change_type": "created|modified|deleted",
  "lines_added": 50,
  "lines_removed": 10,
  "description": "Added new props to Button component"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-project",
    "event_type": "file_changed",
    "data": {
      "file_path": "src/components/Button.tsx",
      "change_type": "modified",
      "lines_added": 25,
      "lines_removed": 5,
      "description": "Added loading state and disabled prop",
      "diff_summary": "+Loading spinner\n+Disabled state styling\n-Old button variant"
    }
  }'
```

---

### 8. activity

General activity log (for debugging or informational messages).

**Data Schema**:
```json
{
  "message": "Activity message",
  "level": "info|debug|warning",
  "metadata": {}
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-project",
    "event_type": "activity",
    "data": {
      "message": "Running type check on modified files",
      "level": "info",
      "metadata": {
        "files_checked": 12,
        "type_errors": 0
      }
    }
  }'
```

---

## Response Endpoints

### Get Response

**GET** `/api/responses/{decision_id}`

Poll for human response to a decision or approval request.

**Response** (pending): `200 OK`
```json
{
  "decision_id": "DEC-001",
  "status": "pending",
  "created_at": "2026-02-11T10:00:00Z"
}
```

**Response** (answered): `200 OK`
```json
{
  "decision_id": "DEC-001",
  "status": "answered",
  "response": "yes",
  "answered_at": "2026-02-11T10:02:00Z",
  "answered_by": "user@example.com",
  "notes": "Proceed with the refactoring"
}
```

**Response** (timeout): `200 OK`
```json
{
  "decision_id": "DEC-001",
  "status": "timeout",
  "default_response": "no",
  "created_at": "2026-02-11T10:00:00Z"
}
```

**Example - Polling Loop**:
```bash
# Request decision
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-project",
    "event_type": "decision_needed",
    "data": {
      "decision_id": "DEC-001",
      "question": "Proceed with migration?",
      "options": ["yes", "no"],
      "timeout_seconds": 300
    }
  }'

# Poll for response (every 5 seconds)
while true; do
  RESPONSE=$(curl -s http://localhost:8000/api/responses/DEC-001)
  STATUS=$(echo $RESPONSE | jq -r '.status')

  if [ "$STATUS" = "answered" ]; then
    DECISION=$(echo $RESPONSE | jq -r '.response')
    echo "Decision received: $DECISION"
    break
  elif [ "$STATUS" = "timeout" ]; then
    echo "Decision timeout, using default"
    break
  fi

  sleep 5
done
```

---

### List Pending Responses

**GET** `/api/responses/pending`

Get all pending decisions and approvals for human review.

**Response**: `200 OK`
```json
{
  "pending_count": 2,
  "items": [
    {
      "decision_id": "DEC-001",
      "project_id": "my-project",
      "question": "Proceed with migration?",
      "options": ["yes", "no"],
      "created_at": "2026-02-11T10:00:00Z",
      "expires_at": "2026-02-11T10:05:00Z"
    },
    {
      "decision_id": "APR-001",
      "project_id": "my-project",
      "action": "deploy_to_production",
      "risk_level": "high",
      "created_at": "2026-02-11T10:01:00Z"
    }
  ]
}
```

**Example**:
```bash
curl http://localhost:8000/api/responses/pending
```

---

### Submit Response

**POST** `/api/responses/{decision_id}`

Submit a human response to a decision or approval request (typically used by the dashboard UI, but can be used by external systems).

**Request Body**:
```json
{
  "response": "yes",
  "notes": "Optional notes about the decision"
}
```

**Response**: `200 OK`
```json
{
  "decision_id": "DEC-001",
  "status": "answered",
  "response": "yes",
  "answered_at": "2026-02-11T10:02:00Z"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/responses/DEC-001 \
  -H "Content-Type: application/json" \
  -d '{
    "response": "yes",
    "notes": "Approved - proceed with migration"
  }'
```

---

## Typical Workflow

Here's a typical workflow for integrating Claude Code with the AI Coding Dashboard:

### 1. Initialize Project

```bash
# Create project on dashboard
PROJECT_ID="claude-$(date +%s)"
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"name\": \"Claude Code Session\",
    \"description\": \"Development session tracked via dashboard\"
  }"
```

### 2. Start Task

```bash
# Notify dashboard that work is starting
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"event_type\": \"task_started\",
    \"data\": {
      \"task_id\": \"TASK-001\",
      \"description\": \"Implement new feature\",
      \"category\": \"feature\",
      \"priority\": 1
    }
  }"
```

### 3. Report Progress

```bash
# Log activities as work progresses
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"event_type\": \"file_changed\",
    \"data\": {
      \"file_path\": \"src/feature.ts\",
      \"change_type\": \"created\",
      \"lines_added\": 100,
      \"description\": \"Created new feature module\"
    }
  }"
```

### 4. Request Decision (if needed)

```bash
# Ask human for decision
DECISION_ID="DEC-$(date +%s)"
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"event_type\": \"decision_needed\",
    \"data\": {
      \"decision_id\": \"$DECISION_ID\",
      \"question\": \"Should I add TypeScript strict mode?\",
      \"options\": [\"yes\", \"no\"],
      \"timeout_seconds\": 300
    }
  }"

# Wait for response
while true; do
  RESP=$(curl -s http://localhost:8000/api/responses/$DECISION_ID)
  STATUS=$(echo $RESP | jq -r '.status')
  if [ "$STATUS" != "pending" ]; then
    DECISION=$(echo $RESP | jq -r '.response')
    echo "Decision: $DECISION"
    break
  fi
  sleep 5
done
```

### 5. Complete Task

```bash
# Mark task as completed
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"event_type\": \"task_completed\",
    \"data\": {
      \"task_id\": \"TASK-001\",
      \"description\": \"Implemented new feature\",
      \"files_changed\": [\"src/feature.ts\", \"src/index.ts\"],
      \"tests_passed\": true,
      \"test_coverage\": 95.0,
      \"screenshot_evidence\": [\"screenshots/TASK-001-feature.png\"]
    }
  }"
```

### 6. Report Milestones

```bash
# Report major milestones
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"event_type\": \"milestone\",
    \"data\": {
      \"milestone_id\": \"MILE-001\",
      \"title\": \"Feature Complete\",
      \"description\": \"All features implemented and tested\",
      \"percentage\": 100
    }
  }"
```

---

## Integration with Claude Code

Claude Code can use this skill by referencing it in its skill directory structure:

### Skill Location

Place this file at:
```
.claude/skills/coding-dashboard/SKILL.md
```

Claude Code will automatically discover and use skills in the `.claude/skills/` directory.

### Usage in Claude Code Prompts

You can reference this skill in your prompts:

```
Use the coding-dashboard skill to track your progress as you work on this task.
```

Or for specific operations:

```
Before proceeding with this breaking change, use the coding-dashboard skill
to request a decision from the human.
```

### Environment Setup

Create a `.env` file in your project:
```env
DASHBOARD_API_URL=http://localhost:8000
DASHBOARD_PROJECT_ID=my-claude-project
```

Then in your shell scripts or agent code:
```bash
source .env
curl -X POST $DASHBOARD_API_URL/api/events \
  -H "Content-Type: application/json" \
  -d "{\"project_id\": \"$DASHBOARD_PROJECT_ID\", ...}"
```

---

## Troubleshooting

### Connection Refused

**Problem**: `curl: (7) Failed to connect to localhost port 8000`

**Solution**: Ensure the dashboard backend is running:
```bash
cd agent
python main.py
```

Verify it's running by checking: `http://localhost:8000/health`

---

### 404 Not Found

**Problem**: `{"error": "Not Found", "message": "Path /api/events not found"}`

**Solution**: The API endpoints might not be implemented yet. Check the current implementation:
```bash
curl http://localhost:8000/
```

If the endpoints are not available, they may be planned for future implementation. Check the project roadmap or `/docs` endpoint.

---

### Invalid Project ID

**Problem**: `{"error": "Project not found", "project_id": "..."}`

**Solution**: Create the project first using the `/api/projects` endpoint before pushing events.

---

### Response Timeout

**Problem**: Polling for response but it never arrives.

**Solution**:
1. Check the dashboard UI to see if the request is visible
2. Verify the decision_id/approval_id matches
3. Check if the request has timed out: `curl http://localhost:8000/api/responses/{id}`
4. Implement a timeout in your polling loop (don't poll forever)

---

### CORS Errors

**Problem**: Browser console shows CORS policy errors.

**Solution**: The backend is configured to allow CORS from `localhost:3010` and `localhost:3000`. If using a different port, update the CORS configuration in `agent/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:YOUR_PORT"],
    ...
)
```

---

## API Status and Roadmap

### Currently Implemented

- `/health` - Health check endpoint
- `/` - API information endpoint
- `/docs` - OpenAPI documentation

### Planned (Check `/docs` for current status)

- `/api/projects` - Project management
- `/api/events` - Event tracking
- `/api/responses` - Decision/approval responses
- WebSocket support for real-time updates

**Note**: Some endpoints in this documentation may be planned features. Always check `http://localhost:8000/docs` for the current API specification.

---

## Examples

### Full Integration Script

Here's a complete bash script demonstrating the full integration:

```bash
#!/bin/bash

# Configuration
DASHBOARD_URL="http://localhost:8000"
PROJECT_ID="claude-integration-demo-$(date +%s)"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Creating project...${NC}"
curl -X POST $DASHBOARD_URL/api/projects \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"name\": \"Integration Demo\",
    \"description\": \"Demonstrating dashboard integration\"
  }"
echo

echo -e "${BLUE}Starting task...${NC}"
curl -X POST $DASHBOARD_URL/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"event_type\": \"task_started\",
    \"data\": {
      \"task_id\": \"DEMO-001\",
      \"description\": \"Build demo feature\",
      \"category\": \"feature\",
      \"priority\": 1
    }
  }"
echo

echo -e "${BLUE}Simulating work...${NC}"
sleep 2

echo -e "${BLUE}Logging file change...${NC}"
curl -X POST $DASHBOARD_URL/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"event_type\": \"file_changed\",
    \"data\": {
      \"file_path\": \"src/demo.ts\",
      \"change_type\": \"created\",
      \"lines_added\": 50,
      \"description\": \"Created demo module\"
    }
  }"
echo

echo -e "${BLUE}Requesting decision...${NC}"
DECISION_ID="DEC-$(date +%s)"
curl -X POST $DASHBOARD_URL/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"event_type\": \"decision_needed\",
    \"data\": {
      \"decision_id\": \"$DECISION_ID\",
      \"question\": \"Add comprehensive test suite?\",
      \"options\": [\"yes\", \"no\"],
      \"timeout_seconds\": 60
    }
  }"
echo

echo -e "${BLUE}Waiting for decision (60s timeout)...${NC}"
TIMEOUT=60
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
  RESPONSE=$(curl -s $DASHBOARD_URL/api/responses/$DECISION_ID)
  STATUS=$(echo $RESPONSE | jq -r '.status')

  if [ "$STATUS" = "answered" ]; then
    DECISION=$(echo $RESPONSE | jq -r '.response')
    echo -e "${GREEN}Decision received: $DECISION${NC}"
    break
  elif [ "$STATUS" = "timeout" ]; then
    echo "Decision timeout"
    break
  fi

  sleep 5
  ELAPSED=$((ELAPSED + 5))
done

echo -e "${BLUE}Completing task...${NC}"
curl -X POST $DASHBOARD_URL/api/events \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"event_type\": \"task_completed\",
    \"data\": {
      \"task_id\": \"DEMO-001\",
      \"description\": \"Built demo feature\",
      \"files_changed\": [\"src/demo.ts\", \"src/demo.test.ts\"],
      \"tests_passed\": true,
      \"test_coverage\": 100
    }
  }"
echo

echo -e "${GREEN}Demo complete!${NC}"
echo "View project at: $DASHBOARD_URL/api/projects/$PROJECT_ID"
```

Save this as `demo_integration.sh` and run:
```bash
chmod +x demo_integration.sh
./demo_integration.sh
```

---

## Support

For issues or questions:
- Check the API documentation: `http://localhost:8000/docs`
- Review the troubleshooting section above
- Check the project repository for updates
- File an issue on the project's issue tracker

---

## License

This skill documentation is part of the AI Coding Dashboard project and follows the same license (MIT).
