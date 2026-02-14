"""Verification script to confirm metrics types are properly defined."""

import metrics

print("Successfully imported metrics module")
print(f"AgentEvent: {metrics.AgentEvent}")
print(f"AgentProfile: {metrics.AgentProfile}")
print(f"SessionSummary: {metrics.SessionSummary}")
print(f"DashboardState: {metrics.DashboardState}")
print("\nAll TypedDict definitions are valid and accessible!")
