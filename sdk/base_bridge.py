"""BaseBridge ABC — re-exported for custom AI provider bridge development."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseBridge(ABC):
    """Abstract base class for custom AI provider bridges in the SDK.

    Implementors must subclass :class:`BaseBridge` and implement the three
    abstract members: :attr:`name`, :meth:`generate`, and
    :meth:`get_model_info`.

    Example::

        class MyBridge(BaseBridge):
            @property
            def name(self) -> str:
                return "my-provider"

            def generate(self, prompt: str, model: str) -> str:
                return call_my_api(prompt, model)

            def get_model_info(self) -> dict:
                return {"provider": "my-provider", "models": ["gpt-x"]}
    """

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this bridge (e.g. ``"openai"``)."""
        ...

    @abstractmethod
    def generate(self, prompt: str, model: str) -> str:
        """Generate a text completion for *prompt* using *model*.

        Parameters
        ----------
        prompt:
            The user / system prompt to complete.
        model:
            Provider-specific model identifier or one of the platform tier
            aliases (``"haiku"`` / ``"sonnet"`` / ``"opus"``).

        Returns
        -------
        str
            The generated text.
        """
        ...

    @abstractmethod
    def get_model_info(self) -> dict[str, Any]:
        """Return a dict describing available models for this bridge.

        The dict must have at least the keys ``"provider"`` and ``"models"``.
        """
        ...

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def format_system_prompt(
        self, system_prompt: str, task_context: dict[str, Any]
    ) -> str:
        """Interpolate *task_context* values into *system_prompt*.

        Placeholders use the ``{key}`` format.  Missing keys in
        *task_context* are left as-is so that partially-filled templates do
        not raise exceptions.

        Parameters
        ----------
        system_prompt:
            Template string, e.g. ``"You are working on ticket {ticket_id}."``
        task_context:
            Mapping of placeholder names to values.

        Returns
        -------
        str
            The formatted system prompt.
        """
        result = system_prompt
        for key, value in task_context.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return result
