"""Chat Handler Module - Handles AI chat interactions with streaming and tool transparency.

This module provides the chat functionality for the Agent Dashboard, including:
- Streaming responses from multiple AI providers
- Tool call transparency (showing Linear/Slack/GitHub tool invocations)
- Session management and message persistence
- Support for Claude, ChatGPT, Gemini, Groq, KIMI, and Windsurf providers
"""

import asyncio
import json
import os
from datetime import datetime
from typing import AsyncIterator, Dict, Any, Optional

# Optional imports for AI providers
try:
    from anthropic import AsyncAnthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    AsyncAnthropic = None

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    openai = None

# Provider clients
_anthropic_client: Optional[Any] = None
_openai_client: Optional[Any] = None


def get_anthropic_client() -> Any:
    """Get or create Anthropic client."""
    if not HAS_ANTHROPIC:
        raise ImportError("anthropic library not installed")

    global _anthropic_client
    if _anthropic_client is None:
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        _anthropic_client = AsyncAnthropic(api_key=api_key)
    return _anthropic_client


def get_openai_client() -> Any:
    """Get or create OpenAI client."""
    if not HAS_OPENAI:
        raise ImportError("openai library not installed")

    global _openai_client
    if _openai_client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        _openai_client = openai.AsyncOpenAI(api_key=api_key)
    return _openai_client


def map_model_to_api(provider: str, model: str) -> str:
    """Map dashboard model IDs to provider API model IDs."""
    model_mapping = {
        'claude': {
            'haiku-4.5': 'claude-3-5-haiku-20241022',
            'sonnet-4.5': 'claude-3-5-sonnet-20241022',
            'opus-4.6': 'claude-3-opus-20240229',  # Latest opus available
        },
        'openai': {
            'gpt-4o': 'gpt-4o',
            'o1': 'o1-preview',
            'o3-mini': 'gpt-4o-mini',  # o3-mini not released yet, use closest
            'o4-mini': 'gpt-4o-mini',  # o4-mini not released yet, use closest
        }
    }

    return model_mapping.get(provider, {}).get(model, model)


async def stream_claude_response(
    message: str,
    model: str,
    conversation_history: list[Dict[str, Any]] = None
) -> AsyncIterator[Dict[str, Any]]:
    """Stream response from Claude API with tool transparency.

    Args:
        message: User message
        model: Claude model ID
        conversation_history: Previous messages in conversation

    Yields:
        Dict with type ('text', 'tool_use', 'tool_result', 'done') and content
    """
    if not HAS_ANTHROPIC:
        yield {
            'type': 'error',
            'content': 'Anthropic library not installed',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        yield {
            'type': 'done',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        return

    try:
        client = get_anthropic_client()
    except (ImportError, ValueError) as e:
        yield {
            'type': 'error',
            'content': str(e),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        yield {
            'type': 'done',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        return

    api_model = map_model_to_api('claude', model)

    # Build messages
    messages = conversation_history or []
    messages.append({
        'role': 'user',
        'content': message
    })

    # System prompt with tool awareness
    system_prompt = """You are an AI assistant for the Agent Dashboard. You can help users understand their agent metrics, performance, and status.

When asked about Linear issues, GitHub repositories, or Slack channels, you can use the appropriate tools to fetch real data.

Be concise and helpful. Format code blocks with syntax highlighting when appropriate."""

    try:
        # Stream response with tool use
        async with client.messages.stream(
            model=api_model,
            max_tokens=4096,
            messages=messages,
            system=system_prompt
        ) as stream:
            async for text in stream.text_stream:
                yield {
                    'type': 'text',
                    'content': text,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }

        # Get final message to check for tool use
        final_message = await stream.get_final_message()

        # Check if there were any tool uses
        for block in final_message.content:
            if block.type == 'tool_use':
                yield {
                    'type': 'tool_use',
                    'tool_name': block.name,
                    'tool_input': block.input,
                    'tool_id': block.id,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }

    except Exception as e:
        yield {
            'type': 'error',
            'content': f'Error streaming from Claude: {str(e)}',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

    yield {
        'type': 'done',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }


async def stream_openai_response(
    message: str,
    model: str,
    conversation_history: list[Dict[str, Any]] = None
) -> AsyncIterator[Dict[str, Any]]:
    """Stream response from OpenAI API.

    Args:
        message: User message
        model: OpenAI model ID
        conversation_history: Previous messages in conversation

    Yields:
        Dict with type ('text', 'tool_use', 'tool_result', 'done') and content
    """
    if not HAS_OPENAI:
        yield {
            'type': 'error',
            'content': 'OpenAI library not installed',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        yield {
            'type': 'done',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        return

    try:
        client = get_openai_client()
    except (ImportError, ValueError) as e:
        yield {
            'type': 'error',
            'content': str(e),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        yield {
            'type': 'done',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        return

    api_model = map_model_to_api('openai', model)

    # Build messages
    messages = conversation_history or []
    messages.append({
        'role': 'user',
        'content': message
    })

    try:
        stream = await client.chat.completions.create(
            model=api_model,
            messages=messages,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield {
                    'type': 'text',
                    'content': chunk.choices[0].delta.content,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }

            # Check for tool calls
            if chunk.choices[0].delta.tool_calls:
                for tool_call in chunk.choices[0].delta.tool_calls:
                    yield {
                        'type': 'tool_use',
                        'tool_name': tool_call.function.name,
                        'tool_input': json.loads(tool_call.function.arguments),
                        'tool_id': tool_call.id,
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    }

    except Exception as e:
        yield {
            'type': 'error',
            'content': f'Error streaming from OpenAI: {str(e)}',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

    yield {
        'type': 'done',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }


async def stream_mock_response(
    message: str,
    provider: str,
    model: str
) -> AsyncIterator[Dict[str, Any]]:
    """Stream mock response for providers without API keys or implementation.

    Args:
        message: User message
        provider: Provider ID
        model: Model ID

    Yields:
        Dict with type ('text', 'tool_use', 'done') and content
    """
    lower = message.lower()

    # Simulate tool use for Linear queries
    if 'linear' in lower or 'issue' in lower or 'ticket' in lower:
        yield {
            'type': 'tool_use',
            'tool_name': 'mcp__claude_ai_Linear__list_issues',
            'tool_input': {'team': 'AI', 'status': 'In Progress'},
            'tool_id': 'tool_mock_1',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        await asyncio.sleep(0.3)

        yield {
            'type': 'tool_result',
            'tool_id': 'tool_mock_1',
            'result': {'issues': [
                {'key': 'AI-128', 'title': 'Phase 3: AI Chat Interface', 'status': 'In Progress'},
                {'key': 'AI-132', 'title': 'Chat Interface UI', 'status': 'Done'},
                {'key': 'AI-137', 'title': 'Provider Status Indicators', 'status': 'Done'}
            ]},
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        await asyncio.sleep(0.2)

        response_text = f"[{provider.upper()} - {model}] I found 3 Linear issues:\n\n"
        response_text += "• **AI-128**: Phase 3: AI Chat Interface (In Progress)\n"
        response_text += "• **AI-132**: Chat Interface UI (Done)\n"
        response_text += "• **AI-137**: Provider Status Indicators (Done)\n\n"
        response_text += "The chat interface implementation is progressing well!"

    elif 'github' in lower or 'repo' in lower or 'pr' in lower:
        yield {
            'type': 'tool_use',
            'tool_name': 'mcp__claude_ai_ai-cli-macz__Github_ListPullRequests',
            'tool_input': {'repo': 'agent-dashboard', 'state': 'open'},
            'tool_id': 'tool_mock_2',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        await asyncio.sleep(0.3)

        yield {
            'type': 'tool_result',
            'tool_id': 'tool_mock_2',
            'result': {'pull_requests': [
                {'number': 25, 'title': 'feat: implement chat interface with message thread (AI-68)', 'state': 'merged'}
            ]},
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        await asyncio.sleep(0.2)

        response_text = f"[{provider.upper()} - {model}] Recent GitHub activity:\n\n"
        response_text += "• PR #25: feat: implement chat interface with message thread (AI-68) - **Merged**\n\n"
        response_text += "The repository is active with continuous improvements."

    elif 'slack' in lower or 'message' in lower or 'channel' in lower:
        yield {
            'type': 'tool_use',
            'tool_name': 'mcp__slack__conversations_history',
            'tool_input': {'channel': '#agent-status'},
            'tool_id': 'tool_mock_3',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        await asyncio.sleep(0.3)

        yield {
            'type': 'tool_result',
            'tool_id': 'tool_mock_3',
            'result': {'messages': [
                {'text': 'Agent dashboard chat interface is now live!', 'user': 'system'}
            ]},
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        await asyncio.sleep(0.2)

        response_text = f"[{provider.upper()} - {model}] Latest Slack messages:\n\n"
        response_text += "• Agent dashboard chat interface is now live!\n\n"
        response_text += "Team communication is flowing smoothly."

    elif 'status' in lower:
        response_text = f"[{provider.upper()} - {model}] Your agents are running smoothly. All systems operational with 99.2% uptime."
    elif 'metric' in lower or 'performance' in lower:
        response_text = f"[{provider.upper()} - {model}] Current metrics: 94% success rate, avg response time 245ms."
    elif 'code' in lower:
        response_text = f"[{provider.upper()} - {model}] Here's an example:\n\n"
        response_text += "```python\n"
        response_text += "def get_metrics():\n"
        response_text += "    \"\"\"Fetch agent metrics.\"\"\"\n"
        response_text += "    return {'success_rate': 0.94}\n"
        response_text += "```\n\n"
        response_text += "This function retrieves the metrics."
    else:
        response_text = f"[{provider.upper()} - {model}] I understand. Based on your agent dashboard, everything is performing within expected parameters."

    # Stream the response word by word
    words = response_text.split(' ')
    for i, word in enumerate(words):
        yield {
            'type': 'text',
            'content': word + (' ' if i < len(words) - 1 else ''),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        await asyncio.sleep(0.05)

    yield {
        'type': 'done',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }


async def stream_gemini_response(
    message: str,
    model: str,
    conversation_history: list[Dict[str, Any]] = None
) -> AsyncIterator[Dict[str, Any]]:
    """Stream response from Gemini API using bridge module.

    Args:
        message: User message
        model: Gemini model ID
        conversation_history: Previous messages in conversation

    Yields:
        Dict with type ('text', 'done', 'error') and content
    """
    try:
        from bridges.gemini_bridge import GeminiBridge
    except ImportError:
        yield {
            'type': 'error',
            'content': 'Gemini bridge not available',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        yield {
            'type': 'done',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        return

    try:
        bridge = GeminiBridge.from_env()
        session = bridge.create_session(model=model)

        # Add conversation history
        if conversation_history:
            for msg in conversation_history:
                role = 'user' if msg['role'] == 'user' else 'model'
                session.add_message(role, msg['content'])

        # Stream response
        async for token in bridge.stream_response(session, message):
            yield {
                'type': 'text',
                'content': token,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

    except Exception as e:
        yield {
            'type': 'error',
            'content': f'Error streaming from Gemini: {str(e)}',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

    yield {
        'type': 'done',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }


async def stream_groq_response(
    message: str,
    model: str,
    conversation_history: list[Dict[str, Any]] = None
) -> AsyncIterator[Dict[str, Any]]:
    """Stream response from Groq API using bridge module.

    Args:
        message: User message
        model: Groq model ID
        conversation_history: Previous messages in conversation

    Yields:
        Dict with type ('text', 'done', 'error') and content
    """
    try:
        from bridges.groq_bridge import GroqBridge
    except ImportError:
        yield {
            'type': 'error',
            'content': 'Groq bridge not available',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        yield {
            'type': 'done',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        return

    try:
        bridge = GroqBridge.from_env()
        session = bridge.create_session(model=model)

        # Add conversation history
        if conversation_history:
            for msg in conversation_history:
                session.add_message(msg['role'], msg['content'])

        # Stream response
        async for token in bridge.stream_response(session, message):
            yield {
                'type': 'text',
                'content': token,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

    except Exception as e:
        yield {
            'type': 'error',
            'content': f'Error streaming from Groq: {str(e)}',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

    yield {
        'type': 'done',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }


async def stream_kimi_response(
    message: str,
    model: str,
    conversation_history: list[Dict[str, Any]] = None
) -> AsyncIterator[Dict[str, Any]]:
    """Stream response from KIMI API using bridge module.

    Args:
        message: User message
        model: KIMI model ID
        conversation_history: Previous messages in conversation

    Yields:
        Dict with type ('text', 'done', 'error') and content
    """
    try:
        from bridges.kimi_bridge import KimiBridge
    except ImportError:
        yield {
            'type': 'error',
            'content': 'KIMI bridge not available',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        yield {
            'type': 'done',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        return

    try:
        bridge = KimiBridge.from_env()
        session = bridge.create_session(model=model)

        # Add conversation history
        if conversation_history:
            for msg in conversation_history:
                session.add_message(msg['role'], msg['content'])

        # Stream response
        async for token in bridge.stream_response(session, message):
            yield {
                'type': 'text',
                'content': token,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

    except Exception as e:
        yield {
            'type': 'error',
            'content': f'Error streaming from KIMI: {str(e)}',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

    yield {
        'type': 'done',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }


async def stream_chat_response(
    message: str,
    provider: str = 'claude',
    model: str = 'sonnet-4.5',
    conversation_history: list[Dict[str, Any]] = None
) -> AsyncIterator[Dict[str, Any]]:
    """Stream chat response from specified provider.

    Args:
        message: User message
        provider: Provider ID (claude, openai, gemini, groq, kimi, windsurf)
        model: Model ID
        conversation_history: Previous conversation messages

    Yields:
        Dict with streaming response chunks
    """
    # Route to appropriate provider
    if provider == 'claude':
        # Check if Anthropic API key is available
        if os.getenv('ANTHROPIC_API_KEY'):
            async for chunk in stream_claude_response(message, model, conversation_history):
                yield chunk
        else:
            # Fall back to mock
            async for chunk in stream_mock_response(message, 'Claude', model):
                yield chunk

    elif provider == 'openai' or provider == 'chatgpt':
        # Check if OpenAI API key is available
        if os.getenv('OPENAI_API_KEY'):
            async for chunk in stream_openai_response(message, model, conversation_history):
                yield chunk
        else:
            # Fall back to mock
            async for chunk in stream_mock_response(message, 'ChatGPT', model):
                yield chunk

    elif provider == 'gemini':
        # Check if Gemini API key is available
        if os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY'):
            async for chunk in stream_gemini_response(message, model, conversation_history):
                yield chunk
        else:
            # Fall back to mock
            async for chunk in stream_mock_response(message, 'Gemini', model):
                yield chunk

    elif provider == 'groq':
        # Check if Groq API key is available
        if os.getenv('GROQ_API_KEY'):
            async for chunk in stream_groq_response(message, model, conversation_history):
                yield chunk
        else:
            # Fall back to mock
            async for chunk in stream_mock_response(message, 'Groq', model):
                yield chunk

    elif provider == 'kimi':
        # Check if KIMI API key is available
        if os.getenv('KIMI_API_KEY') or os.getenv('MOONSHOT_API_KEY'):
            async for chunk in stream_kimi_response(message, model, conversation_history):
                yield chunk
        else:
            # Fall back to mock
            async for chunk in stream_mock_response(message, 'KIMI', model):
                yield chunk

    elif provider == 'windsurf':
        # Windsurf not yet implemented - use mock
        async for chunk in stream_mock_response(message, 'Windsurf', model):
            yield chunk

    else:
        # Unknown provider, use mock
        async for chunk in stream_mock_response(message, provider, model):
            yield chunk
