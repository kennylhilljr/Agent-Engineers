# AI Agent Workflow Guidelines

## Report Generation Standards

All AI agents MUST follow these guidelines when generating reports:

### 1. Use Proper Report Directory

- **NEVER** create files in project root
- **ALWAYS** use `docs/reports/` for implementation reports
- **ALWAYS** use `scripts/report_generator.py` utilities

### 2. Approved File Patterns

```text
docs/reports/AI-{issue_id}_IMPLEMENTATION_REPORT.md
docs/reports/AI-{issue_id}_DELIVERY_SUMMARY.md  
docs/reports/AI-{issue_id}_TEST_REPORT.md
docs/reports/AI-{issue_id}_SUMMARY.json
```

### 3. Forbidden Actions

- ❌ Creating AI-*.md files in project root
- ❌ Creating *_IMPLEMENTATION_* files in project root
- ❌ Creating *_DELIVERY_* files in project root
- ❌ Creating *_FINAL_* files in project root
- ❌ Creating screenshots in project root

### 4. Required Code Pattern

```python
from scripts.report_generator import create_implementation_report

# Instead of: write_to_file("AI-123_IMPLEMENTATION_REPORT.md", content)
# Use: 
file_path = create_implementation_report("123", content)
```

### 5. Git Commit Standards

- Only commit source code changes
- Never commit generated reports to feature branches
- Reports are automatically ignored by .gitignore

### 6. Testing

- Test files go in `tests/` directory
- Test results go in `test-results/` directory
- Screenshots go in `screenshots/` directory

## Enforcement

These rules are enforced by:

1. `.gitignore` patterns
2. `agent_config.py` validation
3. `scripts/report_generator.py` utilities
4. PR review checklists

## Consequences

Violations will result in:

- PR rejection with "CHANGES REQUESTED"
- Required cleanup before re-submission
- Blocked merge until compliance
