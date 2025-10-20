from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

# Define an abstract interface for text generation clients so different
# implementations (local, remote, mock) can be used interchangeably.


class TextGenerationClient(ABC):
    """Abstract interface for a text generation client.

    Implementations must provide synchronous generation methods
    used by the rest of the application.
    """

    @property
    @abstractmethod
    def supports_structured_output(self) -> bool:  # pragma: no cover - interface
        """Return True when structured output (Instructor) is available."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Any:  # Concrete implementations should return a GenerationResult-like object
        """Generate free-form text from a prompt."""

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_model: Any,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Any:
        """Generate structured output (parsed to the provided response_model).

        Should raise RuntimeError if structured output is not supported.
        """
