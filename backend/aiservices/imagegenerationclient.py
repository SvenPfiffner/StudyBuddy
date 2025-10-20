from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

class ImageGenerationClient(ABC):
    """Abstract interface for an image generation client.

    Implementations must provide synchronous generation methods
    used by the rest of the application.
    """


    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate an image from a prompt."""