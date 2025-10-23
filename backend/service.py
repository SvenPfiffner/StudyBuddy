"""Domain logic for converting StudyBuddy requests into LLM prompts."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from textwrap import dedent
from typing import Any, List, Type

from fastapi import HTTPException, status

from .config import Settings, get_settings
from .utils import (
    fix_markdown,
    validate_exam_questions
)
from .prompts import (
    get_generate_exam_prompt,
    get_generate_flashcards_prompt,
    get_generate_summary_prompt,
    get_chat_prompt
)
from .aiservices.localimagegenerationclient import LocalImageGenerationClient
from .aiservices.vllmtextgenerationclient import GenerationResult, VLLMTextGenerationClient
from .aiservices.openaitextgenerationclient import OpenAITextGenerationClient
from .schemas import (
    ChatMessage,
    ExamQuestion,
    ExamQuestionList,
    Flashcard,
    FlashcardList,
)

logger = logging.getLogger(__name__)


class StudyBuddyService:
    """High-level orchestrator for the generative AI services."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if settings.use_external_text_api:
            self._text_client = OpenAITextGenerationClient(self.settings)
        else:
            self._text_client = VLLMTextGenerationClient(self.settings)
        self._image_client = LocalImageGenerationClient(self.settings)

    # ------------------------------------------------------------------
    # Flashcards
    # ------------------------------------------------------------------
    def generate_flashcards(self, script_content: str) -> List[Flashcard]:
        prompt = get_generate_flashcards_prompt(script_content)
        structured = self._maybe_generate_structured(
            prompt,
            FlashcardList,
            max_new_tokens=20192,  # Increased for large structured JSON responses
            temperature=0.0,
        )
        # If structured came back as a model, dict, or JSON string — normalize it.
        if structured is not None:
            try:
                if isinstance(structured, FlashcardList):
                    data = structured
                elif isinstance(structured, str):
                    data = FlashcardList.model_validate_json(structured)
                else:  # dict-like
                    data = FlashcardList.model_validate(structured)

                return data.flashcards
            except Exception as exc:
                logger.warning("Failed to parse structured flashcards: %s", exc)

        return [Flashcard(question="Error", answer="Could not generate flashcards.")]

    # ------------------------------------------------------------------
    # Practice Exam
    # ------------------------------------------------------------------
    def generate_practice_exam(self, script_content: str) -> List[ExamQuestion]:
        prompt = get_generate_exam_prompt(script_content)
        structured = self._maybe_generate_structured(
            prompt,
            ExamQuestionList,
            max_new_tokens=20192,  # Increased for large structured JSON responses
            temperature=0.0,
        )
        # If structured came back as a model, dict, or JSON string — normalize it.
        if structured is not None:
            try:
                if isinstance(structured, ExamQuestionList):
                    data = structured
                elif isinstance(structured, str):
                    data = ExamQuestionList.model_validate_json(structured)
                else:  # dict-like
                    data = ExamQuestionList.model_validate(structured)

                return validate_exam_questions(data.questions)
            except Exception as exc:
                logger.warning("Failed to parse structured exam questions: %s", exc)

        return [ExamQuestion(question="Error", options=["Could not generate exam questions."], correctAnswer="Could not generate exam questions.")]

    # ------------------------------------------------------------------
    # Summary + images
    # ------------------------------------------------------------------
    def generate_summary_with_images(self, script_content: str) -> str:
        prompt = get_generate_summary_prompt(script_content)
        # Generate with lower temperature for more factual output
        result = self._text_client.generate(
            prompt=prompt,
            max_new_tokens=1024,
            temperature=0.3,
        )
        
        markdown = result.text

        markdown = fix_markdown(markdown)
        
        return markdown

    # ------------------------------------------------------------------
    # Image Generation
    # ------------------------------------------------------------------
    def generate_image(self, prompt: str) -> str:
        """Generate a single image from a text prompt and return as base64."""
        if not self.settings.enable_image_generation:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image generation is disabled in the current configuration.",
            )
        
        # Simplify and truncate prompt if too long
        # SDXL models work best with prompts under 77 tokens (~300 chars)
        if len(prompt) > 300:
            logger.warning(f"Image prompt too long ({len(prompt)} chars), truncating")
            # Take first sentence or first 250 chars
            first_sentence = prompt.split('.')[0]
            if len(first_sentence) < 250:
                prompt = first_sentence + "."
            else:
                prompt = prompt[:250] + "..."
        
        try:
            return self._image_client.generate(prompt)
        except Exception as exc:
            logger.exception("Image generation failed for prompt '%s'", prompt)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Image generation failed: {exc}",
            ) from exc

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------
    def continue_chat(self, history: List[ChatMessage], system_instruction: str, message: str) -> str:
        conversation = self._render_history(history)
        prompt = get_chat_prompt(system_instruction, message, conversation)
        print("Prompt for chat continuation:\n", prompt)
        result = self._text_client.generate(prompt, max_new_tokens=512)
        response = result.text
        
        # Clean up any meta-commentary
        cleanup_patterns = [
            r"---\s*Human:.*$",
            r"---\s*Please.*$",
            r"---\s*Remember.*$",
            r"---\s*Note:.*$",
        ]
        
        for pattern in cleanup_patterns:
            response = re.sub(pattern, "", response, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        response = self._strip_hallucinated_turns(response)
        return response.strip()

    def continue_chat_conversational(self, history: List[ChatMessage], context: str, message: str) -> str:
        """
        Use vLLM's conversational API for more robust multi-turn conversations.
        
        Args:
            history: List of ChatMessage objects with role and parts
            context: Document content to use as context
            message: The new user message
            
        Returns:
            The assistant's response text
        """
        # Convert ChatMessage format to dict format expected by generate_conversational
        conversation_messages = []
        for chat_msg in history:
            # Extract text from parts
            content = " ".join(part.text for part in chat_msg.parts)
            # Map "model" role back to "assistant" for the conversational API
            role = "assistant" if chat_msg.role == "model" else chat_msg.role
            if role in {"user", "assistant"}:
                conversation_messages.append({"role": role, "content": content})
        
        result = self._text_client.generate_conversational(
            context=context,
            conversation_messages=conversation_messages,
            user_message=message,
            max_new_tokens=512,
            temperature=0.25,
        )
        return result.text



    # ------------------------------------------------------------------
    # Internal generation helpers
    # ------------------------------------------------------------------
    def _maybe_generate_structured(self, prompt: str, response_model: Any, max_new_tokens: int, temperature: float = 0.7):
        if not self._text_client.supports_structured_output:
            return None
        try:
            return self._text_client.generate_structured(
                prompt=prompt,
                response_model=response_model,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            logger.warning("Structured generation failed: %s", exc)
            return None

    @staticmethod
    def _render_history(history: List[ChatMessage]) -> str:
        rendered_turns: List[str] = []
        for entry in history:
            speaker = "User" if entry.role == "user" else "Assistant"
            for part in entry.parts:
                rendered_turns.append(f"{speaker}: {part.text}")
        return "\n".join(rendered_turns)

    @staticmethod
    def _strip_hallucinated_turns(text: str) -> str:
        """Trim model outputs that fabricate additional conversation turns."""
        text = text.strip()
        if not text:
            return text

        # Drop an initial assistant label if the model echoes the role.
        leading_label = re.compile(r"^[^\S\n]*(?:Assistant|StudyBuddy|Tutor)\s*:\s*", re.IGNORECASE)
        text = re.sub(leading_label, "", text, count=1)

        # Cut off once the model starts inventing a new turn label.
        turn_marker = re.compile(
            r"\n[^\S\n]*(?:User|Human|Student|Teacher|System|Assistant)\s*:",
            re.IGNORECASE,
        )
        match = turn_marker.search(text)
        if match:
            text = text[:match.start()].rstrip()

        return text


@lru_cache
def get_studybuddy_service() -> StudyBuddyService:
    return StudyBuddyService(get_settings())
