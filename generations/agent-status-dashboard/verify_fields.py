"""Verify all required fields are present in TypedDict definitions."""

from typing import get_type_hints
from metrics import AgentEvent, AgentProfile, SessionSummary, DashboardState

print("=== AgentEvent Fields ===")
agent_event_fields = list(get_type_hints(AgentEvent).keys())
print(f"Total fields: {len(agent_event_fields)}")
for field in agent_event_fields:
    print(f"  - {field}")

print("\n=== AgentProfile Fields ===")
agent_profile_fields = list(get_type_hints(AgentProfile).keys())
print(f"Total fields: {len(agent_profile_fields)}")
for field in agent_profile_fields:
    print(f"  - {field}")

print("\n=== SessionSummary Fields ===")
session_summary_fields = list(get_type_hints(SessionSummary).keys())
print(f"Total fields: {len(session_summary_fields)}")
for field in session_summary_fields:
    print(f"  - {field}")

print("\n=== DashboardState Fields ===")
dashboard_state_fields = list(get_type_hints(DashboardState).keys())
print(f"Total fields: {len(dashboard_state_fields)}")
for field in dashboard_state_fields:
    print(f"  - {field}")

print("\n=== Verification Summary ===")
print(f"AgentEvent: {len(agent_event_fields)} fields (expected: 15)")
print(f"AgentProfile: {len(agent_profile_fields)} fields (expected: 33)")
print(f"SessionSummary: {len(session_summary_fields)} fields (expected: 10)")
print(f"DashboardState: {len(dashboard_state_fields)} fields (expected: 11)")

# Verify expected field counts
assert len(agent_event_fields) == 15, f"AgentEvent has {len(agent_event_fields)} fields, expected 15"
assert len(agent_profile_fields) == 33, f"AgentProfile has {len(agent_profile_fields)} fields, expected 33"
assert len(session_summary_fields) == 10, f"SessionSummary has {len(session_summary_fields)} fields, expected 10"
assert len(dashboard_state_fields) == 11, f"DashboardState has {len(dashboard_state_fields)} fields, expected 11"

print("\nAll field counts match specification!")
