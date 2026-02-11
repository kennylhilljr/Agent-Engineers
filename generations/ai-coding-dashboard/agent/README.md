# AI Coding Dashboard - Pydantic AI Agent Backend

This directory contains the Python backend for the AI Coding Dashboard, built with FastAPI and Pydantic AI.

## Setup

### 1. Create Virtual Environment

```bash
cd agent
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Run the Server

```bash
# Development mode (with auto-reload)
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --port 8000
```

The backend will be available at:
- API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc

## Project Structure

```
agent/
├── __init__.py           # Package initialization
├── main.py               # FastAPI application
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
├── .gitignore            # Git ignore rules
├── README.md             # This file
└── test_agent_setup.py   # Comprehensive test suite
```

## API Endpoints

### Health Check
```bash
GET /health
```

Returns server status and version information.

### Root
```bash
GET /
```

Returns API metadata and available endpoints.

### AG-UI Stream (Placeholder)
```bash
POST /ag-ui/stream
```

Placeholder for AG-UI protocol streaming endpoint (will be implemented in KAN-52+).

## Testing

Run the comprehensive test suite:

```bash
# Install test dependencies (already in requirements.txt)
pip install pytest pytest-asyncio httpx

# Run tests
pytest test_agent_setup.py -v

# Run tests with coverage
pytest test_agent_setup.py -v --cov=. --cov-report=html
```

## Development

### Adding New Endpoints

1. Define Pydantic models for request/response validation
2. Create endpoint function with proper type hints
3. Add documentation via docstrings
4. Write tests in `test_agent_setup.py`

### Environment Variables

See `.env.example` for all available configuration options:
- `ENVIRONMENT` - development/production
- `BACKEND_PORT` - Server port (default: 8000)
- `FRONTEND_PORT` - Frontend port for CORS (default: 3010)
- `OPENAI_API_KEY` - OpenAI API key (optional)
- `ANTHROPIC_API_KEY` - Anthropic API key (optional)

## Next Steps

This is foundational setup (KAN-50). Future tasks will add:
- **KAN-52+**: Pydantic AI agent implementation
- **KAN-XX**: AG-UI protocol integration
- **KAN-XX**: CopilotKit frontend integration
- **KAN-XX**: Database integration
- **KAN-XX**: Authentication & authorization

## Technology Stack

- **FastAPI** - Modern, fast web framework
- **Pydantic AI** - AI agent framework with type safety
- **Pydantic** - Data validation using Python type hints
- **Uvicorn** - ASGI server
- **python-dotenv** - Environment variable management

## License

Part of the AI Coding Dashboard project.
