# Agent Dashboard REST API Documentation

**Version:** 1.0
**AI Issue:** AI-197
**Last Updated:** 2026-02-18

## Overview

The Agent Dashboard REST API provides endpoints for monitoring and controlling AI agents,
querying metrics, and sending chat messages through the AI provider bridge.

## Base URL

```
http://localhost:8080
```

## Authentication

Optional bearer token authentication via `DASHBOARD_AUTH_TOKEN` environment variable.

```
Authorization: Bearer <token>
```

If `DASHBOARD_AUTH_TOKEN` is not set, all endpoints are open (development mode).
The `/api/health` endpoint is always unauthenticated.

---

## Endpoints

### Health Check

**GET /api/health**

Returns server health status. Always unauthenticated.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0",
  "timestamp": "2026-02-18T00:00:00Z"
}
```

---

### Metrics

**GET /api/metrics**

Returns current DashboardState metrics.

**Response:**
```json
{
  "agents": [...],
  "active_sessions": 0,
  "timestamp": "2026-02-18T00:00:00Z"
}
```

---

### Agents

**GET /api/agents**

Returns all agent profiles.

**GET /api/agents/{name}**

Returns a single agent profile by name.

**Path Parameters:**
- `name` (string): Agent name (e.g., `linear`, `coding`, `github`)

**GET /api/agents/{name}/events**

Returns recent events for an agent.

---

### Agent Control

**POST /api/agents/{name}/pause**

Pause a running agent.

**POST /api/agents/{name}/resume**

Resume a paused agent.

---

### Sessions

**GET /api/sessions**

Returns session history.

---

### Providers

**GET /api/providers**

Returns available AI providers and their availability status.

**Response:**
```json
{
  "providers": [
    {"name": "claude", "available": true},
    {"name": "chatgpt", "available": false},
    {"name": "gemini", "available": false},
    {"name": "groq", "available": false},
    {"name": "kimi", "available": false},
    {"name": "windsurf", "available": false}
  ]
}
```

---

### Chat

**POST /api/chat**

Send a chat message and receive a streaming response.

**Request Body:**
```json
{
  "message": "What is AI-109 status?",
  "provider": "claude",
  "session_id": "optional-session-id"
}
```

**Response:** Server-Sent Events (SSE) stream or JSON response.

---

### Requirements

**GET /api/requirements/{ticket_key}**

Get current requirement instructions for a ticket.

**PUT /api/requirements/{ticket_key}**

Update requirement instructions for a ticket.

**Path Parameters:**
- `ticket_key` (string): Linear ticket key (e.g., `AI-109`, `PROJ-42`)

---

### Decisions

**GET /api/decisions**

Returns the decision history log.

---

## Error Responses

All endpoints return standard error responses:

```json
{
  "error": "error_type",
  "message": "Human-readable error message",
  "status": 400
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad Request
- `401` - Unauthorized (auth token required but missing/invalid)
- `404` - Not Found
- `500` - Internal Server Error

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_HOST` | `127.0.0.1` | Server bind address |
| `DASHBOARD_WEB_PORT` | `8080` | Server port |
| `DASHBOARD_AUTH_TOKEN` | `` | Bearer token (empty = auth disabled) |
| `DASHBOARD_CORS_ORIGINS` | `*` | CORS allowed origins |
| `DASHBOARD_BROADCAST_INTERVAL` | `5` | WebSocket broadcast interval (seconds) |
