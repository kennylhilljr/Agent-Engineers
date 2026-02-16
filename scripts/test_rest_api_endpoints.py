#!/usr/bin/env python3
"""Manual integration test script for REST API endpoints.

This script starts the REST API server and tests all 14 endpoints manually
using Python's HTTP client. It verifies responses, status codes, and data structure.

Usage:
    python scripts/test_rest_api_endpoints.py
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from threading import Thread

import aiohttp

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.rest_api_server import RESTAPIServer


def create_test_metrics_file(temp_dir: Path):
    """Create a test metrics file with sample data."""
    metrics_file = temp_dir / ".agent_metrics.json"

    mock_metrics = {
        "version": 1,
        "project_name": "test-project",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
        "total_sessions": 5,
        "total_tokens": 10000,
        "total_cost_usd": 0.5,
        "total_duration_seconds": 120.0,
        "agents": {
            "coding": {
                "agent_name": "coding",
                "total_invocations": 10,
                "successful_invocations": 8,
                "failed_invocations": 2,
                "total_tokens": 5000,
                "total_cost_usd": 0.25,
                "total_duration_seconds": 60.0,
                "commits_made": 3,
                "prs_created": 1,
                "prs_merged": 0,
                "files_created": 2,
                "files_modified": 5,
                "lines_added": 150,
                "lines_removed": 30,
                "tests_written": 4,
                "issues_created": 0,
                "issues_completed": 1,
                "messages_sent": 0,
                "reviews_completed": 0,
                "success_rate": 0.8,
                "avg_duration_seconds": 6.0,
                "avg_tokens_per_call": 500.0,
                "cost_per_success_usd": 0.03125,
                "xp": 250,
                "level": 3,
                "current_streak": 2,
                "best_streak": 5,
                "achievements": ["first_commit", "test_writer"],
                "strengths": ["code_quality", "testing"],
                "weaknesses": ["error_handling"],
                "recent_events": ["event-1", "event-2"],
                "last_error": "File not found",
                "last_active": "2024-01-01T12:00:00Z"
            }
        },
        "events": [
            {
                "event_id": "event-1",
                "agent_name": "coding",
                "session_id": "session-1",
                "ticket_key": "AI-100",
                "started_at": "2024-01-01T10:00:00Z",
                "ended_at": "2024-01-01T10:05:00Z",
                "duration_seconds": 300.0,
                "status": "success",
                "input_tokens": 1000,
                "output_tokens": 1500,
                "total_tokens": 2500,
                "estimated_cost_usd": 0.0525,
                "artifacts": ["file:test.py:created"],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
                "file_changes": []
            }
        ],
        "sessions": [
            {
                "session_id": "session-1",
                "session_number": 1,
                "session_type": "initializer",
                "started_at": "2024-01-01T10:00:00Z",
                "ended_at": "2024-01-01T10:30:00Z",
                "status": "complete",
                "agents_invoked": ["coding"],
                "total_tokens": 5000,
                "total_cost_usd": 0.25,
                "tickets_worked": ["AI-100"]
            }
        ]
    }

    metrics_file.write_text(json.dumps(mock_metrics, indent=2))
    return metrics_file


async def test_all_endpoints():
    """Test all REST API endpoints."""
    # Create temporary directory for test metrics
    temp_dir = Path(tempfile.mkdtemp())
    metrics_file = create_test_metrics_file(temp_dir)

    # Create server instance
    port = 18420  # Use different port to avoid conflicts
    server = RESTAPIServer(
        project_name="test-project",
        metrics_dir=temp_dir,
        port=port,
        host="127.0.0.1"
    )

    # Start server in background thread
    server_thread = Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server to start
    time.sleep(2)

    base_url = f"http://127.0.0.1:{port}"

    print("=" * 70)
    print("REST API Endpoint Integration Tests")
    print("=" * 70)
    print()

    passed = 0
    failed = 0

    async with aiohttp.ClientSession() as session:
        # Test 1: GET /api/health
        print("[1] Testing GET /api/health")
        try:
            async with session.get(f"{base_url}/api/health") as resp:
                assert resp.status == 200, f"Expected 200, got {resp.status}"
                data = await resp.json()
                assert data["status"] == "ok", "Health check failed"
                print("    ✓ Health check passed")
                passed += 1
        except Exception as e:
            print(f"    ✗ Health check failed: {e}")
            failed += 1

        # Test 2: GET /api/metrics
        print("[2] Testing GET /api/metrics")
        try:
            async with session.get(f"{base_url}/api/metrics") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "agents" in data
                assert "events" in data
                assert "sessions" in data
                print("    ✓ Metrics endpoint passed")
                passed += 1
        except Exception as e:
            print(f"    ✗ Metrics endpoint failed: {e}")
            failed += 1

        # Test 3: GET /api/agents
        print("[3] Testing GET /api/agents")
        try:
            async with session.get(f"{base_url}/api/agents") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "agents" in data
                assert data["total_agents"] == 14
                print(f"    ✓ All agents endpoint passed (found {data['total_agents']} agents)")
                passed += 1
        except Exception as e:
            print(f"    ✗ All agents endpoint failed: {e}")
            failed += 1

        # Test 4: GET /api/agents/{name}
        print("[4] Testing GET /api/agents/coding")
        try:
            async with session.get(f"{base_url}/api/agents/coding") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["agent"]["agent_name"] == "coding"
                print("    ✓ Specific agent endpoint passed")
                passed += 1
        except Exception as e:
            print(f"    ✗ Specific agent endpoint failed: {e}")
            failed += 1

        # Test 5: GET /api/agents/{name}/events
        print("[5] Testing GET /api/agents/coding/events")
        try:
            async with session.get(f"{base_url}/api/agents/coding/events") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "events" in data
                print(f"    ✓ Agent events endpoint passed (found {len(data['events'])} events)")
                passed += 1
        except Exception as e:
            print(f"    ✗ Agent events endpoint failed: {e}")
            failed += 1

        # Test 6: GET /api/sessions
        print("[6] Testing GET /api/sessions")
        try:
            async with session.get(f"{base_url}/api/sessions") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "sessions" in data
                print(f"    ✓ Sessions endpoint passed (found {len(data['sessions'])} sessions)")
                passed += 1
        except Exception as e:
            print(f"    ✗ Sessions endpoint failed: {e}")
            failed += 1

        # Test 7: GET /api/providers
        print("[7] Testing GET /api/providers")
        try:
            async with session.get(f"{base_url}/api/providers") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "providers" in data
                print(f"    ✓ Providers endpoint passed (found {len(data['providers'])} providers)")
                passed += 1
        except Exception as e:
            print(f"    ✗ Providers endpoint failed: {e}")
            failed += 1

        # Test 8: POST /api/chat
        print("[8] Testing POST /api/chat")
        try:
            payload = {"message": "Hello", "provider": "claude"}
            async with session.post(f"{base_url}/api/chat", json=payload) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["status"] == "success"
                print("    ✓ Chat endpoint passed")
                passed += 1
        except Exception as e:
            print(f"    ✗ Chat endpoint failed: {e}")
            failed += 1

        # Test 9: POST /api/agents/{name}/pause
        print("[9] Testing POST /api/agents/coding/pause")
        try:
            async with session.post(f"{base_url}/api/agents/coding/pause") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["state"] == "paused"
                print("    ✓ Pause agent endpoint passed")
                passed += 1
        except Exception as e:
            print(f"    ✗ Pause agent endpoint failed: {e}")
            failed += 1

        # Test 10: POST /api/agents/{name}/resume
        print("[10] Testing POST /api/agents/coding/resume")
        try:
            async with session.post(f"{base_url}/api/agents/coding/resume") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["state"] == "idle"
                print("    ✓ Resume agent endpoint passed")
                passed += 1
        except Exception as e:
            print(f"    ✗ Resume agent endpoint failed: {e}")
            failed += 1

        # Test 11: PUT /api/requirements/{ticket_key}
        print("[11] Testing PUT /api/requirements/AI-105")
        try:
            payload = {"requirements": "Test requirement text"}
            async with session.put(f"{base_url}/api/requirements/AI-105", json=payload) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["status"] == "success"
                print("    ✓ Update requirements endpoint passed")
                passed += 1
        except Exception as e:
            print(f"    ✗ Update requirements endpoint failed: {e}")
            failed += 1

        # Test 12: GET /api/requirements/{ticket_key}
        print("[12] Testing GET /api/requirements/AI-105")
        try:
            async with session.get(f"{base_url}/api/requirements/AI-105") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["requirements"] == "Test requirement text"
                print("    ✓ Get requirements endpoint passed")
                passed += 1
        except Exception as e:
            print(f"    ✗ Get requirements endpoint failed: {e}")
            failed += 1

        # Test 13: GET /api/decisions
        print("[13] Testing GET /api/decisions")
        try:
            async with session.get(f"{base_url}/api/decisions") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "decisions" in data
                print(f"    ✓ Decisions endpoint passed (found {len(data['decisions'])} decisions)")
                passed += 1
        except Exception as e:
            print(f"    ✗ Decisions endpoint failed: {e}")
            failed += 1

        # Test 14: GET / (dashboard HTML)
        print("[14] Testing GET /")
        try:
            async with session.get(f"{base_url}/") as resp:
                # 200 or 404 acceptable (depends on whether HTML exists)
                assert resp.status in [200, 404]
                print("    ✓ Dashboard HTML endpoint accessible")
                passed += 1
        except Exception as e:
            print(f"    ✗ Dashboard HTML endpoint failed: {e}")
            failed += 1

        # Test error cases
        print("\n[15] Testing error cases")

        # 404 for non-existent agent
        try:
            async with session.get(f"{base_url}/api/agents/nonexistent") as resp:
                assert resp.status == 404
                print("    ✓ 404 error handling works")
                passed += 1
        except Exception as e:
            print(f"    ✗ 404 error handling failed: {e}")
            failed += 1

        # 400 for missing required field
        try:
            async with session.post(f"{base_url}/api/chat", json={}) as resp:
                assert resp.status == 400
                print("    ✓ 400 error handling works")
                passed += 1
        except Exception as e:
            print(f"    ✗ 400 error handling failed: {e}")
            failed += 1

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    # Print summary
    print()
    print("=" * 70)
    print(f"Test Summary: {passed} passed, {failed} failed out of {passed + failed} tests")
    print("=" * 70)

    return failed == 0


def main():
    """Run integration tests."""
    try:
        success = asyncio.run(test_all_endpoints())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
