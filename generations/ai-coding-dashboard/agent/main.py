"""
AI Coding Dashboard - Pydantic AI Agent Backend
FastAPI application for AI agent orchestration and AG-UI protocol support
"""

import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Application lifespan manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    print("Starting AI Agent Backend...")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Frontend URL: http://localhost:{os.getenv('FRONTEND_PORT', '3010')}")
    print(f"Backend URL: http://localhost:{os.getenv('BACKEND_PORT', '8000')}")

    yield

    # Shutdown
    print("Shutting down AI Agent Backend...")


# Create FastAPI application
app = FastAPI(
    title="AI Coding Dashboard Agent",
    description="Pydantic AI-powered agent backend with AG-UI protocol support",
    version="0.1.0",
    lifespan=lifespan,
)


# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{os.getenv('FRONTEND_PORT', '3010')}",
        "http://localhost:3010",  # Default frontend port
        "http://localhost:3000",  # Alternative Next.js port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response validation
class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    message: str
    version: str
    environment: str


class AGUIStreamRequest(BaseModel):
    """AG-UI stream request model (placeholder)"""
    prompt: str
    context: Dict[str, Any] | None = None
    stream: bool = True


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint to verify backend is running

    Returns:
        HealthResponse: Status information about the backend
    """
    return HealthResponse(
        status="healthy",
        message="AI Agent Backend is running",
        version="0.1.0",
        environment=os.getenv("ENVIRONMENT", "development"),
    )


# Root endpoint with API information
@app.get("/")
async def root():
    """
    Root endpoint providing API information

    Returns:
        Dict: API metadata and available endpoints
    """
    return {
        "name": "AI Coding Dashboard Agent",
        "version": "0.1.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "ag_ui_stream": "/ag-ui/stream (coming soon)",
        },
        "documentation": "/docs",
    }


# AG-UI Stream endpoint (placeholder for future implementation)
@app.post("/ag-ui/stream")
async def ag_ui_stream(request: AGUIStreamRequest):
    """
    AG-UI protocol streaming endpoint (placeholder)

    This endpoint will be implemented in later tasks (KAN-52+) to provide
    streaming AI responses using the AG-UI protocol for integration with
    the frontend CopilotKit components.

    Args:
        request: AG-UI stream request with prompt and context

    Returns:
        StreamingResponse: Server-sent events stream with AI responses

    Raises:
        HTTPException: 501 Not Implemented (placeholder)
    """
    # TODO: Implement AG-UI protocol streaming in KAN-52+
    # This is a placeholder that returns a proper HTTP 501 response
    raise HTTPException(
        status_code=501,
        detail={
            "error": "Not Implemented",
            "message": "AG-UI streaming endpoint will be implemented in KAN-52+",
            "received_prompt": request.prompt,
            "stream_requested": request.stream,
        },
    )


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 Not Found errors"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"Path {request.url.path} not found",
            "available_endpoints": ["/", "/health", "/docs", "/ag-ui/stream"],
        },
    )


@app.exception_handler(500)
async def server_error_handler(request, exc):
    """Handle 500 Internal Server Error"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
        },
    )


# Development server runner
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("BACKEND_PORT", "8000"))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    reload = os.getenv("ENVIRONMENT", "development") == "development"

    print(f"\n{'='*50}")
    print("AI Coding Dashboard - Agent Backend")
    print(f"{'='*50}\n")
    print(f"Starting server on {host}:{port}")
    print(f"Docs available at: http://localhost:{port}/docs")
    print(f"Frontend at: http://localhost:{os.getenv('FRONTEND_PORT', '3010')}")
    print(f"\n{'='*50}\n")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
