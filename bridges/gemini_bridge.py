"""
Google Gemini Bridge Module
============================

Wraps Google Gemini interaction to provide a unified interface for the
multi-AI orchestrator. Supports three authentication modes:

1. Gemini CLI OAuth (Primary) - Uses Google's official gemini-cli with OAuth.
   Authenticates via browser; uses Google AI Pro/Ultra subscription credits.
   Zero per-token billing - uses existing web subscription.

2. API Key (Alternative) - Uses google-genai Python SDK with an API key
   from Google AI Studio. Free tier: 60 req/min, 1000 req/day.
   Paid subscription removes limits.

3. Vertex AI (Enterprise) - Uses google-genai SDK with Vertex AI backend.
   Requires Google Cloud project. Pay-as-you-go billing.

Environment Variables:
    GEMINI_AUTH_TYPE: "cli-oauth" (default), "api-key", or "vertex-ai"
    GOOGLE_API_KEY or GEMINI_API_KEY: API key (for api-key auth)
    GOOGLE_CLOUD_PROJECT: GCP project ID (for vertex-ai auth)
    GOOGLE_CLOUD_LOCATION: GCP region (for vertex-ai auth, default: us-central1)
    GEMINI_MODEL: Default model (default: gemini-2.5-flash)
"""

import json
import os
import subprocess
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum


class GeminiAuthType(StrEnum):
    CLI_OAUTH = "cli-oauth"
    API_KEY = "api-key"
    VERTEX_AI = "vertex-ai"


class GeminiModel(StrEnum):
    GEMINI_25_FLASH = "gemini-2.5-flash"
    GEMINI_25_PRO = "gemini-2.5-pro"
    GEMINI_20_FLASH = "gemini-2.0-flash"

    @classmethod
    def from_string(cls, value: str) -> "GeminiModel":
        mapping = {m.value: m for m in cls}
        aliases = {
            "flash": cls.GEMINI_25_FLASH,
            "pro": cls.GEMINI_25_PRO,
            "2.5-flash": cls.GEMINI_25_FLASH,
            "2.5-pro": cls.GEMINI_25_PRO,
            "2.0-flash": cls.GEMINI_20_FLASH,
        }
        key = value.lower().strip()
        return mapping.get(key, aliases.get(key, cls.GEMINI_25_FLASH))


@dataclass
class GeminiMessage:
    role: str
    content: str


@dataclass
class GeminiSession:
    model: GeminiModel
    messages: list[GeminiMessage] = field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(GeminiMessage(role=role, content=content))

    def to_contents(self) -> list[dict]:
        contents = []
        for m in self.messages:
            contents.append({"role": m.role, "parts": [{"text": m.content}]})
        return contents


@dataclass
class GeminiResponse:
    content: str
    model: str
    usage: dict | None = None
    finish_reason: str | None = None


class GeminiCLIClient:
    """Primary path: Uses Google's official gemini-cli with OAuth authentication."""

    def __init__(self):
        if not self._is_gemini_cli_installed():
            raise ImportError(
                "gemini-cli not installed. Run: npm install -g @google/gemini-cli\n"
                "Then run 'gemini' once to complete OAuth setup."
            )

    @staticmethod
    def _is_gemini_cli_installed() -> bool:
        try:
            result = subprocess.run(
                ["gemini", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def send_message(self, session: GeminiSession, message: str) -> GeminiResponse:
        session.add_message("user", message)
        context_parts = []
        for msg in session.messages[:-1]:
            prefix = "User:" if msg.role == "user" else "Gemini:"
            context_parts.append(f"{prefix} {msg.content}")
        if context_parts:
            full_prompt = (
                "Previous conversation:\n" + "\n".join(context_parts) + f"\n\nUser: {message}"
            )
        else:
            full_prompt = message
        try:
            result = subprocess.run(
                [
                    "gemini",
                    "-p",
                    full_prompt,
                    "--model",
                    session.model.value,
                    "--output-format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip() or "gemini-cli returned non-zero exit code"
                raise RuntimeError(f"gemini-cli error: {error_msg}")
            try:
                data = json.loads(result.stdout)
                content = data.get("response", data.get("text", result.stdout.strip()))
            except json.JSONDecodeError:
                content = result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise TimeoutError("gemini-cli timed out after 120 seconds")
        session.add_message("model", content)
        return GeminiResponse(
            content=content, model=session.model.value, usage=None, finish_reason="stop"
        )

    def stream_message(self, session: GeminiSession, message: str) -> str:
        session.add_message("user", message)
        try:
            process = subprocess.Popen(
                [
                    "gemini",
                    "-p",
                    message,
                    "--model",
                    session.model.value,
                    "--output-format",
                    "stream-json",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            full_content = ""
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    chunk = event.get("text", event.get("content", ""))
                    if chunk:
                        full_content += chunk
                except json.JSONDecodeError:
                    full_content += line
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            process.kill()
            raise TimeoutError("gemini-cli stream timed out")
        session.add_message("model", full_content)
        return full_content


class GenAISDKClient:
    """Alternative path: Uses google-genai Python SDK (API key or Vertex AI)."""

    def __init__(self, auth_type: GeminiAuthType):
        try:
            from google import genai

            self._genai = genai
        except ImportError:
            raise ImportError("google-genai package not installed. Run: pip install google-genai")

        if auth_type == GeminiAuthType.API_KEY:
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                raise ValueError(
                    "GOOGLE_API_KEY or GEMINI_API_KEY not set.\nGet a free key from: https://aistudio.google.com/app/apikey"
                )
            self._client = genai.Client(api_key=api_key)
            self._async_client = genai.Client(api_key=api_key).aio
        elif auth_type == GeminiAuthType.VERTEX_AI:
            project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            if not project:
                raise ValueError("GOOGLE_CLOUD_PROJECT not set for Vertex AI auth.")
            self._client = genai.Client(vertexai=True, project=project, location=location)
            self._async_client = genai.Client(vertexai=True, project=project, location=location).aio
        else:
            raise ValueError(f"GenAISDKClient does not support auth type: {auth_type}")

    def send_message(self, session: GeminiSession, message: str) -> GeminiResponse:
        session.add_message("user", message)
        response = self._client.models.generate_content(
            model=session.model.value,
            contents=message if len(session.messages) <= 1 else session.to_contents(),
        )
        content = response.text or ""
        session.add_message("model", content)
        usage = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "prompt_tokens": getattr(um, "prompt_token_count", 0) or 0,
                "completion_tokens": getattr(um, "candidates_token_count", 0) or 0,
                "total_tokens": getattr(um, "total_token_count", 0) or 0,
            }
        return GeminiResponse(
            content=content, model=session.model.value, usage=usage, finish_reason="stop"
        )

    async def send_message_async(self, session: GeminiSession, message: str) -> GeminiResponse:
        session.add_message("user", message)
        response = await self._async_client.models.generate_content(
            model=session.model.value,
            contents=message if len(session.messages) <= 1 else session.to_contents(),
        )
        content = response.text or ""
        session.add_message("model", content)
        usage = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "prompt_tokens": getattr(um, "prompt_token_count", 0) or 0,
                "completion_tokens": getattr(um, "candidates_token_count", 0) or 0,
                "total_tokens": getattr(um, "total_token_count", 0) or 0,
            }
        return GeminiResponse(
            content=content, model=session.model.value, usage=usage, finish_reason="stop"
        )

    async def stream_response(self, session: GeminiSession, message: str) -> AsyncIterator[str]:
        session.add_message("user", message)
        response = await self._async_client.models.generate_content_stream(
            model=session.model.value,
            contents=message if len(session.messages) <= 1 else session.to_contents(),
        )
        full_content = ""
        async for chunk in response:
            if chunk.text:
                full_content += chunk.text
                yield chunk.text
        session.add_message("model", full_content)


class GeminiBridge:
    """Unified bridge for Gemini access."""

    def __init__(self, auth_type: GeminiAuthType, client):
        self.auth_type = auth_type
        self._client = client

    @classmethod
    def from_env(cls) -> "GeminiBridge":
        auth_type_str = os.environ.get("GEMINI_AUTH_TYPE", "cli-oauth")
        try:
            auth_type = GeminiAuthType(auth_type_str.lower().strip())
        except ValueError:
            print(f"Warning: Unknown GEMINI_AUTH_TYPE '{auth_type_str}', falling back to cli-oauth")
            auth_type = GeminiAuthType.CLI_OAUTH
        if auth_type == GeminiAuthType.CLI_OAUTH:
            client = GeminiCLIClient()
        else:
            client = GenAISDKClient(auth_type)
        return cls(auth_type=auth_type, client=client)

    def create_session(
        self, model: str | None = None, system_prompt: str | None = None
    ) -> GeminiSession:
        model_str = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        gemini_model = GeminiModel.from_string(model_str)
        session = GeminiSession(model=gemini_model)
        if system_prompt:
            session.add_message("user", f"System instructions: {system_prompt}")
            session.add_message("model", "Understood. I'll follow those instructions.")
        return session

    def send_message(self, session: GeminiSession, message: str) -> GeminiResponse:
        return self._client.send_message(session, message)

    async def send_message_async(self, session: GeminiSession, message: str) -> GeminiResponse:
        if hasattr(self._client, "send_message_async"):
            return await self._client.send_message_async(session, message)
        return self._client.send_message(session, message)

    async def stream_response(self, session: GeminiSession, message: str) -> AsyncIterator[str]:
        if hasattr(self._client, "stream_response"):
            async for token in self._client.stream_response(session, message):
                yield token
        elif hasattr(self._client, "stream_message"):
            content = self._client.stream_message(session, message)
            yield content
        else:
            response = self._client.send_message(session, message)
            yield response.content

    def get_auth_info(self) -> dict[str, str]:
        info = {
            "auth_type": self.auth_type.value,
            "model_default": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        }
        if self.auth_type == GeminiAuthType.CLI_OAUTH:
            info["cost_note"] = (
                "Using gemini-cli OAuth. Uses Google AI subscription. No per-token billing."
            )
            info["cli_installed"] = "yes" if check_gemini_cli_installed() else "no"
        elif self.auth_type == GeminiAuthType.API_KEY:
            key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
            info["api_key_set"] = "yes" if key else "no"
            info["api_key_prefix"] = key[:8] + "..." if len(key) > 8 else "(short)"
            info["cost_note"] = "Using API key. Free tier: 60 req/min, 1000 req/day."
        elif self.auth_type == GeminiAuthType.VERTEX_AI:
            info["project"] = os.environ.get("GOOGLE_CLOUD_PROJECT", "(not set)")
            info["location"] = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            info["cost_note"] = "Using Vertex AI. Pay-as-you-go billing."
        return info


def check_gemini_cli_installed() -> bool:
    try:
        result = subprocess.run(["gemini", "--version"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_available_models() -> list[str]:
    return [m.value for m in GeminiModel]


def print_auth_status() -> None:
    try:
        bridge = GeminiBridge.from_env()
        info = bridge.get_auth_info()
        print("Gemini Authentication Status:")
        for key, value in info.items():
            print(f"  {key}: {value}")
    except (ValueError, ImportError) as e:
        print(f"Gemini authentication error: {e}")
