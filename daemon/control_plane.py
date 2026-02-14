"""
HTTP Control Plane
==================

A lightweight HTTP server for runtime management of the scalable daemon.
Provides endpoints for health checks, worker status, pool scaling,
and dynamic configuration.

Endpoints:
    GET  /health           — Health check
    GET  /workers          — List all workers and their status
    GET  /pools            — Pool summary
    GET  /queue            — Queue depth
    POST /workers          — Add workers to a pool
    POST /webhook/linear   — Linear webhook receiver (Proposal 9)
    PATCH /pools/<name>    — Resize a pool
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from daemon.worker_pool import WorkerPoolManager

logger = logging.getLogger("control_plane")


class ControlPlane:
    """HTTP control plane for daemon runtime management.

    Uses asyncio's built-in HTTP server capabilities to avoid
    requiring starlette/uvicorn as hard dependencies for the daemon.
    """

    def __init__(
        self,
        pool_manager: WorkerPoolManager,
        port: int = 9100,
    ) -> None:
        self.pool_manager = pool_manager
        self.port = port
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the control plane HTTP server."""
        self._server = await asyncio.start_server(
            self._handle_connection,
            "127.0.0.1",
            self.port,
        )
        logger.info("Control plane listening on http://127.0.0.1:%d", self.port)

    async def stop(self) -> None:
        """Stop the control plane HTTP server."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info("Control plane stopped")

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a single HTTP connection."""
        try:
            # Read the request line and headers
            request_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not request_line:
                writer.close()
                return

            request_str = request_line.decode("utf-8", errors="replace").strip()
            parts = request_str.split(" ")
            if len(parts) < 2:
                await self._send_response(writer, 400, {"error": "Bad request"})
                return

            method = parts[0].upper()
            path = parts[1]

            # Read headers
            content_length = 0
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    break
                if decoded.lower().startswith("content-length:"):
                    content_length = int(decoded.split(":", 1)[1].strip())

            # Read body if present
            body: bytes = b""
            if content_length > 0:
                body = await asyncio.wait_for(
                    reader.readexactly(content_length),
                    timeout=5.0,
                )

            # Route request
            response = self._route(method, path, body)
            await self._send_response(writer, response[0], response[1])

        except (TimeoutError, ConnectionError, asyncio.IncompleteReadError):
            pass
        except Exception as e:
            logger.warning("Control plane request error: %s", e)
            try:
                await self._send_response(writer, 500, {"error": str(e)})
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _route(self, method: str, path: str, body: bytes) -> tuple[int, dict]:
        """Route a request to the appropriate handler."""
        if path == "/health" and method == "GET":
            return self._handle_health()
        elif path == "/workers" and method == "GET":
            return self._handle_get_workers()
        elif path == "/workers" and method == "POST":
            return self._handle_add_workers(body)
        elif path == "/pools" and method == "GET":
            return self._handle_get_pools()
        elif path == "/queue" and method == "GET":
            return self._handle_get_queue()
        elif path == "/webhook/linear" and method == "POST":
            return self._handle_linear_webhook(body)
        elif path.startswith("/pools/") and method == "PATCH":
            pool_name = path.split("/pools/", 1)[1].rstrip("/")
            return self._handle_resize_pool(pool_name, body)
        else:
            return 404, {"error": "Not found"}

    def _handle_health(self) -> tuple[int, dict]:
        """GET /health — Health check."""
        return 200, {"status": "ok"}

    def _handle_get_workers(self) -> tuple[int, dict]:
        """GET /workers — List all workers."""
        workers: list[dict[str, Any]] = []
        for pool_type, pool in self.pool_manager.pools.items():
            for w in pool.workers:
                worker_info: dict[str, Any] = {
                    "worker_id": w.worker_id,
                    "pool": pool_type.value,
                    "status": w.status.value,
                    "tickets_completed": w.tickets_completed,
                    "consecutive_errors": w.consecutive_errors,
                }
                if w.current_ticket:
                    worker_info["current_ticket"] = {
                        "key": w.current_ticket.key,
                        "title": w.current_ticket.title,
                    }
                workers.append(worker_info)
        return 200, {"workers": workers}

    def _handle_add_workers(self, body: bytes) -> tuple[int, dict]:
        """POST /workers — Add workers to a pool."""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return 400, {"error": "Invalid JSON"}

        pool_name = data.get("pool", "coding")
        count = data.get("count", 1)

        from daemon.worker_pool import PoolType

        try:
            pool_type = PoolType(pool_name)
        except ValueError:
            return 400, {"error": f"Unknown pool: {pool_name}"}

        pool = self.pool_manager.pools.get(pool_type)
        if pool is None:
            return 404, {"error": f"Pool '{pool_name}' not found"}

        added = 0
        for _ in range(count):
            worker = pool.add_worker()
            if worker is not None:
                added += 1

        return 200, {
            "added": added,
            "pool": pool_name,
            "total_workers": len(pool.workers),
        }

    def _handle_get_pools(self) -> tuple[int, dict]:
        """GET /pools — Pool summary."""
        return 200, self.pool_manager.status_summary()

    def _handle_get_queue(self) -> tuple[int, dict]:
        """GET /queue — Queue depth and status."""
        return 200, {
            "queue_depth": self.pool_manager.ticket_queue.qsize(),
        }

    def _handle_linear_webhook(self, body: bytes) -> tuple[int, dict]:
        """POST /webhook/linear — Receive Linear webhook events.

        Parses the webhook payload and enqueues actionable tickets.
        Linear webhooks send JSON with action, type, and data fields.
        """
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return 400, {"error": "Invalid JSON"}

        action = data.get("action", "")
        obj_type = data.get("type", "")

        # Only process issue state changes
        if obj_type != "Issue":
            return 200, {"status": "ignored", "reason": f"type={obj_type}"}

        issue_data = data.get("data", {})
        state_name = issue_data.get("state", {}).get("name", "").lower()

        # Enqueue tickets that are actionable (moved to Todo or back to Todo)
        actionable_states = ("todo", "backlog", "triage")
        if action in ("create", "update") and state_name in actionable_states:
            from daemon.worker_pool import Ticket

            ticket = Ticket(
                key=issue_data.get("identifier", issue_data.get("id", "UNKNOWN")),
                title=issue_data.get("title", "Untitled"),
                description=issue_data.get("description", ""),
                status="todo",
                priority=str(issue_data.get("priority", "medium")),
                labels=[
                    node.get("name", "") for node in issue_data.get("labels", {}).get("nodes", [])
                ],
            )

            self.pool_manager.ticket_queue.put_nowait(ticket)
            logger.info(
                "Webhook: enqueued %s '%s' (action=%s, state=%s)",
                ticket.key,
                ticket.title,
                action,
                state_name,
            )
            return 200, {"status": "enqueued", "ticket": ticket.key}

        return 200, {"status": "ignored", "reason": f"action={action}, state={state_name}"}

    def _handle_resize_pool(self, pool_name: str, body: bytes) -> tuple[int, dict]:
        """PATCH /pools/<name> — Resize a pool."""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return 400, {"error": "Invalid JSON"}

        from daemon.worker_pool import PoolType

        try:
            pool_type = PoolType(pool_name)
        except ValueError:
            return 400, {"error": f"Unknown pool: {pool_name}"}

        max_workers = data.get("max_workers")
        if max_workers is None or not isinstance(max_workers, int) or max_workers < 1:
            return 400, {"error": "max_workers must be a positive integer"}

        try:
            self.pool_manager.resize_pool(pool_type, max_workers)
        except KeyError:
            return 404, {"error": f"Pool '{pool_name}' not found"}

        pool = self.pool_manager.pools[pool_type]
        return 200, {
            "pool": pool_name,
            "max_workers": max_workers,
            "current_workers": len(pool.workers),
        }

    @staticmethod
    async def _send_response(
        writer: asyncio.StreamWriter,
        status: int,
        body: dict,
    ) -> None:
        """Send an HTTP response with JSON body."""
        status_text = {
            200: "OK",
            400: "Bad Request",
            404: "Not Found",
            500: "Internal Server Error",
        }
        body_bytes = json.dumps(body, indent=2).encode("utf-8")
        response = (
            f"HTTP/1.1 {status} {status_text.get(status, 'Unknown')}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode() + body_bytes
        writer.write(response)
        await writer.drain()
