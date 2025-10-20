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
from .aiservices.localtextgenerationclient import GenerationResult, LocalTextGenerationClient
from .schemas import (
    ChatMessage,
    ExamQuestion,
    ExamResponse,
    Flashcard,
    FlashcardResponse,
)

logger = logging.getLogger(__name__)


class StudyBuddyService:
    """High-level orchestrator for all API endpoints."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._text_client = LocalTextGenerationClient(self.settings)
        self._image_client = LocalImageGenerationClient(self.settings)

    # ------------------------------------------------------------------
    # Flashcards
    # ------------------------------------------------------------------
    def generate_flashcards(self, script_content: str) -> List[Flashcard]:
        prompt = get_generate_flashcards_prompt(script_content)
        structured = self._maybe_generate_structured(
            prompt,
            list[Flashcard],
            max_new_tokens=1024,
            temperature=0.0,
        )
        if structured is not None:
            try:
                if isinstance(structured, list):
                    return [Flashcard.model_validate(item) for item in structured]
                # Instructor may wrap the payload in a dict; attempt to extract generically.
                if isinstance(structured, dict):
                    # Prefer common keys
                    for key in ("flashcards", "items", "data", "result"):
                        if key in structured and isinstance(structured[key], list):
                            return [Flashcard.model_validate(item) for item in structured[key]]
                # Fallback: validate via FlashcardResponse RootModel
                return list(FlashcardResponse.model_validate(structured).root)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to interpret structured flashcards: %s", exc)
        return self._generate_json_with_retry(
            prompt,
            Flashcard,
            max_new_tokens=1024,
        )

    # ------------------------------------------------------------------
    # Practice Exam
    # ------------------------------------------------------------------
    def generate_practice_exam(self, script_content: str) -> List[ExamQuestion]:
        prompt = get_generate_exam_prompt(script_content)
        structured = self._maybe_generate_structured(
            prompt,
            list[ExamQuestion],
            max_new_tokens=2048,
            temperature=0.0,
        )
        if structured is not None:
            try:
                if isinstance(structured, list):
                    questions = [ExamQuestion.model_validate(item) for item in structured]
                elif isinstance(structured, dict):
                    for key in ("questions", "items", "data", "result"):
                        if key in structured and isinstance(structured[key], list):
                            questions = [ExamQuestion.model_validate(item) for item in structured[key]]
                            break
                    else:
                        questions = list(ExamResponse.model_validate(structured).root)
                else:
                    questions = list(ExamResponse.model_validate(structured).root)
                return self.validate_exam_questions(questions)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to interpret structured exam output: %s", exc)
        questions = self._generate_json_with_retry(
            prompt,
            ExamQuestion,
            max_new_tokens=2048,
        )
        return validate_exam_questions(questions)

    # ------------------------------------------------------------------
    # Summary + images
    # ------------------------------------------------------------------
    def generate_summary_with_images(self, script_content: str) -> str:
        prompt = get_generate_summary_prompt(script_content)
        # Use lower temperature for more consistent formatting
        result = self._safe_generate(prompt, max_new_tokens=1024, temperature=0.3)
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
        result = self._safe_generate(prompt, max_new_tokens=512)
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

    def _generate_json_with_retry(
        self,
        prompt: str,
        model_cls: Type[Any],
        max_new_tokens: int,
    ):
        # Always use temperature=0.0 for structured JSON output to reduce hallucinations
        try:
            result = self._safe_generate(prompt, max_new_tokens=max_new_tokens, temperature=0.0)
            return self._parse_json_array(result.text, model_cls)
        except HTTPException as first_error:
            logger.warning("Retrying JSON generation with stricter instructions.")
            refined_prompt = (
                f"{prompt.rstrip()}\n\n"
                "CRITICAL: Return ONLY a valid JSON array starting with [ and ending with ]. "
                "Do not add any text before or after. Do not use code fences."
            )
            retry = self._safe_generate(
                refined_prompt,
                max_new_tokens=max_new_tokens,
                temperature=0.0,
            )
            try:
                return self._parse_json_array(retry.text, model_cls)
            except HTTPException:
                raise first_error

    def _safe_generate(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float | None = None,
    ) -> GenerationResult:
        try:
            return self._text_client.generate(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
            )
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - depends on runtime
            logger.exception("Text generation failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Text generation failed: {exc}",
            ) from exc

    def _parse_json_array(self, payload: str, model_cls):
        try:
            data = json.loads(self._extract_json(payload))
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON payload: %s", payload)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The language model returned malformed JSON.",
            ) from exc
        if not isinstance(data, list):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The language model returned a payload that was not a JSON array.",
            )
        return [model_cls(**item) for item in data]

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        
        # Look for code fences anywhere in the text, not just at the start
        fence_start = text.find("```")
        if fence_start != -1:
            # Find the end of the opening fence (could be ```json or just ```)
            first_newline = text.find("\n", fence_start)
            if first_newline != -1:
                # Find the closing fence
                fence_end = text.find("```", first_newline)
                if fence_end != -1:
                    return text[first_newline + 1:fence_end].strip()
        
        # If no code fence found, try to find JSON array or object
        # Look for opening [ or {
        json_start = -1
        for char in ['[', '{']:
            idx = text.find(char)
            if idx != -1 and (json_start == -1 or idx < json_start):
                json_start = idx
        
        if json_start == -1:
            return text
        
        # Now find the matching closing bracket/brace
        # Use a simple bracket matcher to handle nested structures
        extracted = text[json_start:]
        bracket_count = 0
        in_string = False
        escape_next = False
        open_char = extracted[0]
        close_char = ']' if open_char == '[' else '}'
        
        for i, char in enumerate(extracted):
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not in_string:
                in_string = True
            elif char == '"' and in_string:
                in_string = False
            elif not in_string:
                if char in '[{':
                    bracket_count += 1
                elif char in ']}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        # Found the matching closing bracket
                        return extracted[:i+1].strip()
        
        # If we didn't find a closing bracket, return from start to end
        return extracted.strip()

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
def get_service() -> StudyBuddyService:
    return StudyBuddyService(get_settings())
