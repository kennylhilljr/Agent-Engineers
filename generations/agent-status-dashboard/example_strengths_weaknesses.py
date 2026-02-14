"""Example usage of strengths/weaknesses detection.

This script demonstrates how to use the strengths/weaknesses detection
system to analyze agent performance and automatically identify their
characteristics.
"""

from datetime import datetime, timedelta
from metrics import AgentEvent, DashboardState
from strengths_weaknesses import (
    update_agent_strengths_weaknesses,
    get_strength_description,
    get_weakness_description,
)
from agent_metrics_collector import _create_empty_profile


def create_example_event(
    agent_name: str,
    status: str = "success",
    duration_seconds: float = 60.0,
    cost_usd: float = 0.01,
    tokens: int = 1000,
    artifacts: list = None,
) -> AgentEvent:
    """Helper to create example events."""
    now = datetime.utcnow()
    return {
        "event_id": f"event-{agent_name}-{now.timestamp()}",
        "agent_name": agent_name,
        "session_id": "example-session",
        "ticket_key": "AI-48",
        "started_at": now.isoformat() + "Z",
        "ended_at": (now + timedelta(seconds=duration_seconds)).isoformat() + "Z",
        "duration_seconds": duration_seconds,
        "status": status,
        "input_tokens": tokens // 2,
        "output_tokens": tokens // 2,
        "total_tokens": tokens,
        "estimated_cost_usd": cost_usd,
        "artifacts": artifacts or [],
        "error_message": "" if status == "success" else "Example error",
        "model_used": "claude-sonnet-4-5",
    }


def main():
    """Run example demonstration."""
    print("=" * 80)
    print("Agent Strengths/Weaknesses Detection Example")
    print("=" * 80)
    print()

    # Create a dashboard state with example agents
    now = datetime.utcnow().isoformat() + "Z"
    state: DashboardState = {
        "version": 1,
        "project_name": "example-project",
        "created_at": now,
        "updated_at": now,
        "total_sessions": 1,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "total_duration_seconds": 0.0,
        "agents": {},
        "events": [],
        "sessions": [],
    }

    # Agent 1: "speed_demon" - fast, cheap, successful
    print("Creating events for 'speed_demon' agent (fast & cheap)...")
    state["agents"]["speed_demon"] = _create_empty_profile("speed_demon")
    for i in range(20):
        event = create_example_event(
            "speed_demon",
            status="success",
            duration_seconds=15.0,
            cost_usd=0.002,
            artifacts=["file:fast.py", "commit:abc123"]
        )
        state["events"].append(event)

    # Agent 2: "reliable_robot" - consistent, high success rate
    print("Creating events for 'reliable_robot' agent (consistent & reliable)...")
    state["agents"]["reliable_robot"] = _create_empty_profile("reliable_robot")
    for i in range(20):
        event = create_example_event(
            "reliable_robot",
            status="success",
            duration_seconds=60.0,  # Always exactly 60s
            cost_usd=0.01,
            artifacts=["file:reliable.py", "test:test_reliable.py"]
        )
        state["events"].append(event)

    # Agent 3: "code_machine" - prolific artifact producer
    print("Creating events for 'code_machine' agent (prolific)...")
    state["agents"]["code_machine"] = _create_empty_profile("code_machine")
    for i in range(20):
        event = create_example_event(
            "code_machine",
            status="success",
            duration_seconds=80.0,
            cost_usd=0.015,
            artifacts=[
                "file:code1.py",
                "file:code2.py",
                "file:code3.py",
                "commit:xyz789",
                "test:test_code.py"
            ]  # 5 artifacts per event
        )
        state["events"].append(event)

    # Agent 4: "slow_poke" - slow and expensive
    print("Creating events for 'slow_poke' agent (slow & expensive)...")
    state["agents"]["slow_poke"] = _create_empty_profile("slow_poke")
    for i in range(20):
        event = create_example_event(
            "slow_poke",
            status="success",
            duration_seconds=200.0,
            cost_usd=0.05,
            artifacts=["file:slow.py"]
        )
        state["events"].append(event)

    # Agent 5: "buggy_bot" - high error rate
    print("Creating events for 'buggy_bot' agent (high error rate)...")
    state["agents"]["buggy_bot"] = _create_empty_profile("buggy_bot")
    for i in range(20):
        status = "success" if i % 3 == 0 else "error"  # 33% success rate
        event = create_example_event(
            "buggy_bot",
            status=status,
            duration_seconds=50.0,
            cost_usd=0.008,
        )
        state["events"].append(event)

    # Agent 6: "wild_card" - inconsistent performance
    print("Creating events for 'wild_card' agent (inconsistent)...")
    state["agents"]["wild_card"] = _create_empty_profile("wild_card")
    durations = [10, 150, 20, 140, 30, 130, 15, 145, 25, 135] * 2
    for i, duration in enumerate(durations):
        event = create_example_event(
            "wild_card",
            status="success",
            duration_seconds=float(duration),
            cost_usd=0.01,
        )
        state["events"].append(event)

    print(f"\nCreated {len(state['events'])} total events for {len(state['agents'])} agents")
    print()

    # Run strengths/weaknesses detection
    print("Running strengths/weaknesses detection...")
    print()
    updated_state = update_agent_strengths_weaknesses(state, window_size=20, min_events=5)

    # Display results
    print("=" * 80)
    print("RESULTS: Agent Performance Analysis")
    print("=" * 80)
    print()

    for agent_name, profile in sorted(updated_state["agents"].items()):
        print(f"Agent: {agent_name}")
        print("-" * 40)

        if profile["strengths"]:
            print(f"  Strengths ({len(profile['strengths'])}):")
            for strength in profile["strengths"]:
                desc = get_strength_description(strength)
                print(f"    - {strength}: {desc}")
        else:
            print("  Strengths: None detected")

        if profile["weaknesses"]:
            print(f"  Weaknesses ({len(profile['weaknesses'])}):")
            for weakness in profile["weaknesses"]:
                desc = get_weakness_description(weakness)
                print(f"    - {weakness}: {desc}")
        else:
            print("  Weaknesses: None detected")

        print()

    # Summary statistics
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_strengths = sum(len(p["strengths"]) for p in updated_state["agents"].values())
    total_weaknesses = sum(len(p["weaknesses"]) for p in updated_state["agents"].values())
    print(f"Total strengths detected: {total_strengths}")
    print(f"Total weaknesses detected: {total_weaknesses}")
    print(f"Average strengths per agent: {total_strengths / len(updated_state['agents']):.2f}")
    print(f"Average weaknesses per agent: {total_weaknesses / len(updated_state['agents']):.2f}")
    print()

    # Find best and worst performers
    agents_by_strength_count = sorted(
        updated_state["agents"].items(),
        key=lambda x: len(x[1]["strengths"]),
        reverse=True
    )
    agents_by_weakness_count = sorted(
        updated_state["agents"].items(),
        key=lambda x: len(x[1]["weaknesses"]),
        reverse=True
    )

    print(f"Top performer: {agents_by_strength_count[0][0]} ({len(agents_by_strength_count[0][1]['strengths'])} strengths)")
    print(f"Needs improvement: {agents_by_weakness_count[0][0]} ({len(agents_by_weakness_count[0][1]['weaknesses'])} weaknesses)")
    print()


if __name__ == "__main__":
    main()
