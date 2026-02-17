# AI Agent Configuration
# This file configures AI agents to use proper directories for reports

# Report output directory - always use this instead of project root
REPORTS_DIR = "docs/reports"

# File patterns that should be ignored in git
IGNORED_PATTERNS = [
    "AI-*.md",
    "AI-*.txt", 
    "AI-*.json",
    "*_IMPLEMENTATION_*",
    "*_DELIVERY_*",
    "*_FINAL_*",
    "*_SUMMARY*",
    "DOCUMENTATION_*",
    "MONITORING.md",
    "VERIFICATION_*",
    "TEST_RESULTS_*"
]

# Approved file locations
APPROVED_LOCATIONS = {
    "reports": "docs/reports/",
    "docs": "docs/",
    "tests": "tests/",
    "test_results": "test-results/"
}

def get_report_path(issue_id: str, report_type: str = "IMPLEMENTATION") -> str:
    """Generate proper path for AI-generated reports"""
    return f"docs/reports/AI-{issue_id}_{report_type}_REPORT.md"

def get_summary_path(issue_id: str, summary_type: str = "DELIVERY") -> str:
    """Generate proper path for AI-generated summaries"""
    return f"docs/reports/AI-{issue_id}_{summary_type}_SUMMARY.md"
