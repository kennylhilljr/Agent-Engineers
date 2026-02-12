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

# A2UI Validator import
from a2ui_validator import A2UIValidator

# Load environment variables
load_dotenv()

# Initialize A2UI Validator (global instance)
a2ui_validator = A2UIValidator()


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


class A2UIValidationRequest(BaseModel):
    """A2UI validation request model"""
    message: Dict[str, Any]


class A2UIValidationResponse(BaseModel):
    """A2UI validation response model"""
    valid: bool
    errors: list[str] = []
    warnings: list[str] | None = None
    message: Dict[str, Any] | None = None


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
            "a2ui_validate": "/a2ui/validate",
            "ag_ui_stream": "/ag-ui/stream (coming soon)",
        },
        "documentation": "/docs",
        "a2ui": {
            "version": "0.8",
            "validator_active": True,
        },
    }


# A2UI Validation endpoint
@app.post("/a2ui/validate", response_model=A2UIValidationResponse)
async def validate_a2ui(request: A2UIValidationRequest):
    """
    Validate A2UI message against v0.8 specification

    Args:
        request: A2UI validation request with message to validate

    Returns:
        A2UIValidationResponse: Validation result with errors/warnings

    Example:
        ```json
        {
          "message": {
            "messageType": "beginRendering",
            "components": [
              {
                "type": "a2ui.Button",
                "id": "btn-1",
                "props": {"text": "Click me"}
              }
            ]
          }
        }
        ```
    """
    result = a2ui_validator.validate_message(request.message)

    return A2UIValidationResponse(
        valid=result.valid,
        errors=result.errors,
        warnings=result.warnings if result.warnings else None,
        message=result.message if result.valid else None,
    )


# AG-UI Stream endpoint (placeholder for future implementation)
@app.post("/ag-ui/stream")
async def ag_ui_stream(request: AGUIStreamRequest):
    """
    AG-UI protocol streaming endpoint (placeholder)

    This endpoint will be implemented in later tasks (KAN-52+) to provide
    streaming AI responses using the AG-UI protocol for integration with
    the frontend CopilotKit components.

    SECURITY: All emitted A2UI messages will be validated before sending to frontend.

    Args:
        request: AG-UI stream request with prompt and context

    Returns:
        StreamingResponse: Server-sent events stream with AI responses

    Raises:
        HTTPException: 501 Not Implemented (placeholder)
    """
    # TODO: Implement AG-UI protocol streaming in KAN-52+
    # TODO: Integrate A2UI validator to validate all emitted messages
    # Example validation:
    #   result = a2ui_validator.validate_message(agent_output)
    #   if not result.valid:
    #       logger.error(f"Invalid A2UI: {result.errors}")
    #       # Reject or sanitize the message

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
