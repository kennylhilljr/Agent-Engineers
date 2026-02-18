#!/usr/bin/env python3
"""
AI Agent Report Generator
========================

Utility functions for AI agents to generate reports in proper locations.
Prevents littering of project root directory.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from agent_config import REPORTS_DIR, get_report_path, get_summary_path


def ensure_reports_dir():
    """Ensure reports directory exists"""
    reports_dir = Path(REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def create_implementation_report(issue_id: str, content: str, title: Optional[str] = None) -> str:
    """Create implementation report in proper location"""
    ensure_reports_dir()
    
    if not title:
        title = f"AI-{issue_id} Implementation Report"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report_content = f"""# {title}

Generated: {timestamp}
Issue ID: AI-{issue_id}

{content}
"""
    
    file_path = get_report_path(issue_id)
    with open(file_path, 'w') as f:
        f.write(report_content)
    
    return file_path


def create_delivery_summary(issue_id: str, content: str, title: Optional[str] = None) -> str:
    """Create delivery summary in proper location"""
    ensure_reports_dir()
    
    if not title:
        title = f"AI-{issue_id} Delivery Summary"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    summary_content = f"""# {title}

Generated: {timestamp}
Issue ID: AI-{issue_id}

{content}
"""
    
    file_path = get_summary_path(issue_id)
    with open(file_path, 'w') as f:
        f.write(summary_content)
    
    return file_path


def create_test_report(issue_id: str, content: str, title: Optional[str] = None) -> str:
    """Create test report in proper location"""
    ensure_reports_dir()
    
    if not title:
        title = f"AI-{issue_id} Test Report"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report_content = f"""# {title}

Generated: {timestamp}
Issue ID: AI-{issue_id}

{content}
"""
    
    file_path = f"docs/reports/AI-{issue_id}_TEST_REPORT.md"
    with open(file_path, 'w') as f:
        f.write(report_content)
    
    return file_path


def validate_file_location(file_path: str) -> bool:
    """Validate that file is being created in approved location"""
    file_path = Path(file_path).resolve()
    
    # Check if file would be in project root
    project_root = Path(__file__).parent.resolve()
    
    try:
        relative_path = file_path.relative_to(project_root)
        
        # Disallow root-level AI files
        if any(pattern.startswith("AI-") for pattern in relative_path.parts):
            return False
            
        # Allow only approved directories
        if relative_path.parts[0] in ["docs", "tests", "test-results"]:
            return True
            
        return False
    except ValueError:
        return False


if __name__ == "__main__":
    # Test the functions
    ensure_reports_dir()
    print("Report generator utilities loaded successfully")
    print(f"Reports directory: {REPORTS_DIR}")
