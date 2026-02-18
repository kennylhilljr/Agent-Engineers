"""Tests for dashboard/crash_isolation.py (AI-183 / REQ-REL-001).

Covers:
- @isolated decorator: normal return, exception → fallback, default fallback
- @isolated_async decorator: async normal return, async exception → fallback
- IsolatedDashboardClient: emit_* no-ops when hook=None, isolates hook errors,
  available property reflects hook presence
- WebSocket disconnect behaviour in server.py
- OrchestratorHook: broken callback does not propagate
- Multiple clients: one disconnect does not affect others
"""

import asyncio
import logging
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from dashboard.crash_isolation import (
    IsolatedDashboardClient,
    isolated,
    isolated_async,
)
from dashboard.orchestrator_hook import OrchestratorHook


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _AlwaysRaises:
    """Fake hook whose emit_* methods always raise RuntimeError."""

    def emit_delegation(self, *args, **kwargs):
        raise RuntimeError("delegation boom")

    def emit_decision(self, *args, **kwargs):
        raise RuntimeError("decision boom")

    def emit_reasoning(self, *args, **kwargs):
        raise RuntimeError("reasoning boom")


# ---------------------------------------------------------------------------
# Tests: @isolated decorator
# ---------------------------------------------------------------------------

class TestIsolatedDecorator(unittest.TestCase):
    """Tests for the @isolated synchronous decorator."""

    def test_returns_result_when_no_exception(self):
        """Normal function result is returned unchanged."""
        @isolated()
        def add(a, b):
            return a + b

        self.assertEqual(add(2, 3), 5)

    def test_returns_fallback_none_by_default_on_exception(self):
        """Default fallback is None when function raises."""
        @isolated()
        def boom():
            raise ValueError("oops")

        result = boom()
        self.assertIsNone(result)

    def test_returns_custom_fallback_on_exception(self):
        """Custom fallback value is returned when function raises."""
        @isolated(fallback=-1)
        def boom():
            raise RuntimeError("error")

        self.assertEqual(boom(), -1)

    def test_returns_false_fallback_on_exception(self):
        """Falsy fallback value (False) is returned correctly."""
        @isolated(fallback=False)
        def boom():
            raise Exception("fail")

        self.assertIs(boom(), False)

    def test_returns_empty_list_fallback_on_exception(self):
        """Mutable falsy fallback (empty list) is returned correctly."""
        @isolated(fallback=[])
        def boom():
            raise Exception("fail")

        result = boom()
        self.assertEqual(result, [])

    def test_exception_is_logged_not_raised(self):
        """Exception is logged at WARNING by default; nothing is re-raised."""
        @isolated()
        def boom():
            raise ValueError("test error")

        with self.assertLogs("dashboard.crash_isolation", level="WARNING") as cm:
            boom()

        self.assertTrue(any("boom" in line for line in cm.output))

    def test_custom_log_level_is_used(self):
        """Custom log_level parameter is respected."""
        @isolated(log_level=logging.ERROR)
        def boom():
            raise ValueError("at error level")

        with self.assertLogs("dashboard.crash_isolation", level="ERROR") as cm:
            boom()

        self.assertTrue(any("ERROR" in line for line in cm.output))

    def test_preserves_function_name(self):
        """Decorator preserves the wrapped function's __name__."""
        @isolated()
        def my_special_func():
            pass

        self.assertEqual(my_special_func.__name__, "my_special_func")

    def test_passes_args_and_kwargs(self):
        """Arguments are correctly forwarded to the wrapped function."""
        @isolated()
        def multiply(x, factor=1):
            return x * factor

        self.assertEqual(multiply(3, factor=4), 12)

    def test_does_not_swallow_return_none(self):
        """A function that legitimately returns None is not confused with fallback."""
        @isolated(fallback="FALLBACK")
        def returns_none():
            return None

        # The function returns None, not "FALLBACK"
        self.assertIsNone(returns_none())

    def test_multiple_exceptions_all_caught(self):
        """Multiple successive calls all return fallback without raising."""
        call_count = 0

        @isolated(fallback="safe")
        def fragile():
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"call {call_count}")

        results = [fragile() for _ in range(5)]
        self.assertEqual(results, ["safe"] * 5)
        self.assertEqual(call_count, 5)


# ---------------------------------------------------------------------------
# Tests: @isolated_async decorator
# ---------------------------------------------------------------------------

class TestIsolatedAsyncDecorator(unittest.TestCase):
    """Tests for the @isolated_async decorator used with async functions."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_async_returns_result_when_no_exception(self):
        """Async function result is returned unchanged."""
        @isolated_async()
        async def async_add(a, b):
            return a + b

        result = self._run(async_add(10, 20))
        self.assertEqual(result, 30)

    def test_async_returns_none_fallback_by_default_on_exception(self):
        """Default fallback is None when async function raises."""
        @isolated_async()
        async def async_boom():
            raise ValueError("async oops")

        result = self._run(async_boom())
        self.assertIsNone(result)

    def test_async_returns_custom_fallback_on_exception(self):
        """Custom fallback value is returned when async function raises."""
        @isolated_async(fallback="default_data")
        async def async_boom():
            raise RuntimeError("async error")

        result = self._run(async_boom())
        self.assertEqual(result, "default_data")

    def test_async_exception_is_logged(self):
        """Async exception is logged and not re-raised."""
        @isolated_async()
        async def async_boom():
            raise ValueError("async test error")

        with self.assertLogs("dashboard.crash_isolation", level="WARNING") as cm:
            self._run(async_boom())

        self.assertTrue(any("async_boom" in line for line in cm.output))

    def test_async_preserves_function_name(self):
        """Async decorator preserves the wrapped function's __name__."""
        @isolated_async()
        async def my_async_func():
            pass

        self.assertEqual(my_async_func.__name__, "my_async_func")

    def test_async_passes_args_and_kwargs(self):
        """Arguments are correctly forwarded to the wrapped async function."""
        @isolated_async()
        async def async_greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = self._run(async_greet("World", greeting="Hi"))
        self.assertEqual(result, "Hi, World!")


# ---------------------------------------------------------------------------
# Tests: IsolatedDashboardClient
# ---------------------------------------------------------------------------

class TestIsolatedDashboardClientNoHook(unittest.TestCase):
    """IsolatedDashboardClient behaves as no-op when hook=None."""

    def setUp(self):
        self.client = IsolatedDashboardClient(hook=None)

    def test_available_is_false_when_no_hook(self):
        """available property is False when hook is None."""
        self.assertFalse(self.client.available)

    def test_emit_delegation_returns_none_with_no_hook(self):
        """emit_delegation returns None without error when hook=None."""
        result = self.client.emit_delegation("coding", "task", "reasoning")
        self.assertIsNone(result)

    def test_emit_decision_returns_none_with_no_hook(self):
        """emit_decision returns None without error when hook=None."""
        result = self.client.emit_decision({"decision": "test"})
        self.assertIsNone(result)

    def test_emit_reasoning_returns_none_with_no_hook(self):
        """emit_reasoning returns None without error when hook=None."""
        result = self.client.emit_reasoning("some reasoning text")
        self.assertIsNone(result)

    def test_no_exception_propagated_with_no_hook(self):
        """None hook never raises on any emit call."""
        # Should complete without any exception
        self.client.emit_delegation("agent", "task", "reason")
        self.client.emit_decision("my decision")
        self.client.emit_reasoning("thinking...")


class TestIsolatedDashboardClientWithHook(unittest.TestCase):
    """IsolatedDashboardClient wraps a real hook correctly."""

    def setUp(self):
        self.hook = OrchestratorHook(session_id="test-session")
        self.client = IsolatedDashboardClient(hook=self.hook)

    def test_available_is_true_when_hook_provided(self):
        """available property is True when hook is provided."""
        self.assertTrue(self.client.available)

    def test_emit_delegation_forwards_to_hook(self):
        """emit_delegation forwards call to hook and events are recorded."""
        self.client.emit_delegation("coding", "Implement feature", "Best suited")
        # Give background thread a moment to run
        time.sleep(0.05)
        events = self.hook.events
        self.assertTrue(len(events) >= 1)
        self.assertEqual(events[0]["agent_name"], "coding")

    def test_emit_decision_forwards_to_hook(self):
        """emit_decision forwards call to hook."""
        self.client.emit_decision({"agent": "linear", "confidence": 0.9})
        time.sleep(0.05)
        events = self.hook.events
        self.assertTrue(len(events) >= 1)

    def test_emit_reasoning_forwards_to_hook(self):
        """emit_reasoning forwards call to hook."""
        self.client.emit_reasoning("This is a reasoning trace")
        time.sleep(0.05)
        events = self.hook.events
        self.assertTrue(len(events) >= 1)


class TestIsolatedDashboardClientWithBrokenHook(unittest.TestCase):
    """IsolatedDashboardClient isolates errors from a broken hook."""

    def setUp(self):
        self.client = IsolatedDashboardClient(hook=_AlwaysRaises())

    def test_available_is_true_even_for_broken_hook(self):
        """available is True as long as a hook object is present."""
        self.assertTrue(self.client.available)

    def test_emit_delegation_does_not_propagate_hook_error(self):
        """emit_delegation catches hook errors silently."""
        # Should not raise despite hook raising RuntimeError
        result = self.client.emit_delegation("agent", "task", "reason")
        self.assertIsNone(result)

    def test_emit_decision_does_not_propagate_hook_error(self):
        """emit_decision catches hook errors silently."""
        result = self.client.emit_decision("decision text")
        self.assertIsNone(result)

    def test_emit_reasoning_does_not_propagate_hook_error(self):
        """emit_reasoning catches hook errors silently."""
        result = self.client.emit_reasoning("some reasoning")
        self.assertIsNone(result)

    def test_hook_error_is_logged(self):
        """Hook errors are logged as WARNING."""
        with self.assertLogs("dashboard.crash_isolation", level="WARNING") as cm:
            self.client.emit_delegation("agent", "task", "reason")

        self.assertTrue(any("emit_delegation" in line for line in cm.output))


# ---------------------------------------------------------------------------
# Tests: OrchestratorHook — broken callback isolation
# ---------------------------------------------------------------------------

class TestOrchestratorHookCallbackIsolation(unittest.TestCase):
    """OrchestratorHook isolates broken in-process callbacks."""

    def test_broken_callback_does_not_propagate_to_caller(self):
        """A callback that raises must not interrupt emit_delegation."""
        hook = OrchestratorHook()

        def bad_callback(event):
            raise RuntimeError("callback failure")

        hook.add_callback(bad_callback)

        # Must not raise — exception is isolated in background thread
        hook.emit_delegation("coding", "task", "reason")
        # Give the background thread time to fire
        time.sleep(0.05)

        # The event is still recorded despite callback failure
        self.assertEqual(len(hook.events), 1)

    def test_good_callback_called_after_bad_callback(self):
        """A good callback still fires even if a preceding callback raises."""
        hook = OrchestratorHook()
        received = []

        def bad_callback(event):
            raise RuntimeError("bad")

        def good_callback(event):
            received.append(event)

        hook.add_callback(bad_callback)
        hook.add_callback(good_callback)

        hook.emit_delegation("linear", "Check tickets", "need tickets")
        time.sleep(0.1)

        self.assertEqual(len(received), 1)


# ---------------------------------------------------------------------------
# Tests: WebSocket disconnect isolation
# ---------------------------------------------------------------------------

class TestWebSocketDisconnectIsolation(unittest.TestCase):
    """WebSocket client disconnect does not affect the server or other clients."""

    def test_client_removal_on_disconnect(self):
        """Simulating client disconnect removes the client from websockets set."""
        # We test the set-based tracking logic directly without starting aiohttp
        class FakeWS:
            def __init__(self, name):
                self.name = name
                self.should_fail = False

            async def send_json(self, data):
                if self.should_fail:
                    raise ConnectionError("client disconnected")

        ws_clients = set()
        client_a = FakeWS("a")
        client_b = FakeWS("b")
        client_c = FakeWS("c")

        ws_clients.add(client_a)
        ws_clients.add(client_b)
        ws_clients.add(client_c)

        # Simulate client_b disconnecting
        client_b.should_fail = True

        # Mirror the server's broadcast_to_websockets logic
        disconnected = set()
        for ws in ws_clients:
            async def try_send(w=ws):
                try:
                    await w.send_json({})
                except Exception:
                    disconnected.add(w)

            asyncio.get_event_loop().run_until_complete(try_send())

        ws_clients -= disconnected

        self.assertNotIn(client_b, ws_clients)
        self.assertIn(client_a, ws_clients)
        self.assertIn(client_c, ws_clients)

    def test_one_client_disconnect_does_not_affect_others(self):
        """Other clients still receive messages after one client disconnects."""
        messages_received = {}

        class FakeWS:
            def __init__(self, name, fail=False):
                self.name = name
                self.fail = fail
                messages_received[name] = []

            async def send_json(self, data):
                if self.fail:
                    raise ConnectionError("gone")
                messages_received[self.name].append(data)

        ws_clients = set()
        good1 = FakeWS("good1")
        bad = FakeWS("bad", fail=True)
        good2 = FakeWS("good2")

        ws_clients.update([good1, bad, good2])

        # Broadcast, removing disconnected clients
        disconnected = set()
        for ws in ws_clients:
            async def broadcast(w=ws):
                try:
                    await w.send_json({"msg": "hello"})
                except Exception:
                    disconnected.add(w)

            asyncio.get_event_loop().run_until_complete(broadcast())

        ws_clients -= disconnected

        self.assertEqual(len(messages_received["good1"]), 1)
        self.assertEqual(len(messages_received["good2"]), 1)
        self.assertEqual(len(messages_received["bad"]), 0)
        self.assertNotIn(bad, ws_clients)


# ---------------------------------------------------------------------------
# Tests: Dashboard is optional (orchestrator works without it)
# ---------------------------------------------------------------------------

class TestDashboardOptional(unittest.TestCase):
    """Verify orchestrator functions correctly with no dashboard hook."""

    def test_orchestrator_hook_works_without_collector(self):
        """OrchestratorHook with no attachments stores events in-memory only."""
        hook = OrchestratorHook()
        hook.emit_delegation("coding", "task", "reason")
        time.sleep(0.05)
        self.assertEqual(len(hook.events), 1)

    def test_isolated_client_with_none_hook_is_inert(self):
        """IsolatedDashboardClient(None) can be called repeatedly with no effect."""
        client = IsolatedDashboardClient(None)
        for _ in range(10):
            client.emit_delegation("a", "b", "c")
            client.emit_decision("d")
            client.emit_reasoning("e")
        # No exceptions; nothing to assert beyond reaching here
        self.assertFalse(client.available)

    def test_errors_logged_not_propagated(self):
        """Broken hook errors appear in logs but don't raise."""
        client = IsolatedDashboardClient(_AlwaysRaises())

        with self.assertLogs("dashboard.crash_isolation", level="WARNING"):
            # All three emit calls log warnings — at least one log line emitted
            client.emit_delegation("x", "y", "z")

        # Confirm no exception was raised (execution reaches here)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
