"""Domain logic for converting StudyBuddy requests into LLM prompts."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import List

from fastapi import HTTPException, status

from .config import Settings, get_settings
from .llm import GenerationResult, ImageGenerationClient, TextGenerationClient
from .schemas import ChatMessage, ExamQuestion, Flashcard

logger = logging.getLogger(__name__)

IMAGE_PROMPT_REGEX = re.compile(r"\[IMAGE_PROMPT:\s*(.*?)\s*\]")


class StudyBuddyService:
    """High-level orchestrator for all API endpoints."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._text_client = TextGenerationClient(self.settings)
        self._image_client = ImageGenerationClient(self.settings)

    # ------------------------------------------------------------------
    # Flashcards
    # ------------------------------------------------------------------
    def generate_flashcards(self, script_content: str) -> List[Flashcard]:
        prompt = (
            "You are an educational assistant. Read the study material below and generate a JSON array of flashcards. "
            "Each entry must have the keys 'question' and 'answer'. Focus on the most important facts, definitions, and concepts.\n\n"
            "Study material:\n" + script_content + "\n\nReturn only valid JSON."
        )
        result = self._safe_generate(prompt, max_new_tokens=768)
        return self._parse_json_array(result.text, Flashcard)

    # ------------------------------------------------------------------
    # Practice Exam
    # ------------------------------------------------------------------
    def generate_practice_exam(self, script_content: str) -> List[ExamQuestion]:
        prompt = (
            "You are preparing a multiple choice practice exam. Based on the study material below, create at least five questions. "
            "Return a JSON array where every object has the keys 'question', 'options' (exactly four), and 'correctAnswer' which must match one of the options.\n\n"
            "Study material:\n" + script_content + "\n\nReturn only valid JSON."
        )
        result = self._safe_generate(prompt, max_new_tokens=1024)
        questions = self._parse_json_array(result.text, ExamQuestion)
        for question in questions:
            if len(question.options) != 4:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Generated exam question does not have exactly four options.",
                )
            if question.correctAnswer not in question.options:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Generated exam question has a correctAnswer that is not one of the options.",
                )
        return questions

    # ------------------------------------------------------------------
    # Summary + images
    # ------------------------------------------------------------------
    def generate_summary_with_images(self, script_content: str) -> str:
        prompt = (
            "Create a structured Markdown summary of the study material below. Write in concise sections with headings and bullet points when useful. "
            "When a visual aid would help, insert a placeholder exactly in the form [IMAGE_PROMPT: description of the scene]. Limit to at most 3 images.\n\n"
            "Study material:\n" + script_content + "\n\nReturn only the Markdown summary."
        )
        result = self._safe_generate(prompt, max_new_tokens=1024)
        markdown = result.text

        prompts = IMAGE_PROMPT_REGEX.findall(markdown)
        if not prompts:
            return markdown

        if not self.settings.enable_image_generation:
            def _disabled(_: re.Match[str]) -> str:
                return (
                    "\n\n<div class=\"my-6 p-4 bg-gray-700/50 border border-blue-500/50 rounded-lg text-center text-blue-200\">"
                    f"<em>Image prompt: {_.group(1).strip()} (image generation disabled)</em></div>\n\n"
                )

            return IMAGE_PROMPT_REGEX.sub(_disabled, markdown)

        replacements: List[str] = []
        for prompt_text in prompts:
            try:
                image_b64 = self._image_client.generate(prompt_text)
                replacements.append(
                    f'\n\n<img src="data:image/jpeg;base64,{image_b64}" alt="{prompt_text}" class="my-6 rounded-lg shadow-lg w-full" />\n\n'
                )
            except Exception as exc:  # pragma: no cover - hardware dependent
                logger.exception("Failed to generate image for prompt '%s'", prompt_text)
                replacements.append(
                    "\n\n<div class=\"my-6 p-4 bg-gray-700/50 border border-red-500/50 rounded-lg text-center text-red-400\"><em>"
                    + f"Image generation failed for prompt: {prompt_text}."
                    + "</em></div>\n\n"
                )

        def _replacement(_: re.Match[str]) -> str:
            return replacements.pop(0) if replacements else ""

        return IMAGE_PROMPT_REGEX.sub(_replacement, markdown)

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------
    def continue_chat(self, history: List[ChatMessage], system_instruction: str, message: str) -> str:
        conversation = self._render_history(history)
        prompt = (
            f"{system_instruction.strip()}\n\n"
            "The following is a conversation between a helpful study assistant and a user. Respond with clear, actionable explanations.\n"
            f"Conversation so far:\n{conversation}\nUser: {message}\nAssistant:"
        )
        result = self._safe_generate(prompt, max_new_tokens=512)
        return result.text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _safe_generate(self, prompt: str, max_new_tokens: int) -> GenerationResult:
        try:
            return self._text_client.generate(prompt, max_new_tokens=max_new_tokens)
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
        if text.startswith("```"):
            fence_end = text.find("```", 3)
            if fence_end != -1:
                return text[3:fence_end].strip()
        return text

    @staticmethod
    def _render_history(history: List[ChatMessage]) -> str:
        rendered_turns: List[str] = []
        for entry in history:
            speaker = "User" if entry.role == "user" else "Assistant"
            for part in entry.parts:
                rendered_turns.append(f"{speaker}: {part.text}")
        return "\n".join(rendered_turns)


@lru_cache
def get_service() -> StudyBuddyService:
    return StudyBuddyService(get_settings())
