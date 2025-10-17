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
            "Return a JSON array where every object has the keys 'question', 'options' (exactly four), and 'correctAnswer' which must be EXACTLY one of the options - copy it verbatim.\n\n"
            "Study material:\n" + script_content + "\n\nReturn only valid JSON."
        )
        result = self._safe_generate(prompt, max_new_tokens=1024)
        questions = self._parse_json_array(result.text, ExamQuestion)
        for idx, question in enumerate(questions):
            if len(question.options) != 4:
                logger.error(
                    "Question %d has %d options instead of 4: %s", 
                    idx, len(question.options), question.options
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Generated exam question {idx+1} does not have exactly four options (has {len(question.options)}).",
                )
            
            # Check if correctAnswer matches any option exactly
            if question.correctAnswer not in question.options:
                # Try to find a fuzzy match (case-insensitive and contains check)
                matched_option = None
                correct_lower = question.correctAnswer.lower()
                
                # First try: find option that contains the correct answer or vice versa
                for option in question.options:
                    option_lower = option.lower()
                    if correct_lower in option_lower or option_lower in correct_lower:
                        matched_option = option
                        break
                
                if matched_option:
                    logger.warning(
                        "Question %d: Fuzzy matched correctAnswer '%s' to option '%s'",
                        idx, question.correctAnswer, matched_option
                    )
                    # Fix the question by setting correctAnswer to the matched option
                    question.correctAnswer = matched_option
                else:
                    logger.error(
                        "Question %d correctAnswer '%s' not in options: %s",
                        idx, question.correctAnswer, question.options
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Generated exam question {idx+1} has a correctAnswer that is not one of the options.",
                    )
        return questions

    # ------------------------------------------------------------------
    # Summary + images
    # ------------------------------------------------------------------
    def generate_summary_with_images(self, script_content: str) -> str:
        prompt = (
            "You are a professional educational content creator. Create a clear, structured Markdown summary of the study material below.\n\n"
            "FORMATTING RULES:\n"
            "- Use headings (##, ###) to organize topics\n"
            "- Use bullet points for lists and key concepts\n"
            "- Write concisely but comprehensively\n"
            "- DO NOT add any meta-commentary, instructions, or notes to the reader\n"
            "- DO NOT write things like 'Please note', 'Remember to', or 'The images should'\n\n"
            "IMAGE PLACEMENT RULES:\n"
            "- Insert [IMAGE_PROMPT: detailed description] ONLY where a visual would genuinely help understanding\n"
            "- Place images AFTER the relevant paragraph or section, never at the beginning\n"
            "- Limit to 2-3 images maximum\n"
            "- Image prompts should describe concrete, specific visuals (diagrams, charts, illustrations)\n"
            "- Example: [IMAGE_PROMPT: A labeled diagram showing the structure of a neuron with dendrites, axon, and synapses]\n\n"
            "Study material:\n" + script_content + "\n\n"
            "Generate the summary now:"
        )
        result = self._safe_generate(prompt, max_new_tokens=1024)
        markdown = result.text
        
        # Clean up any meta-commentary that slipped through
        # Remove common hallucinated phrases
        cleanup_patterns = [
            r"---\s*Human:.*$",
            r"---\s*Please note.*$",
            r"---\s*Remember.*$",
            r"Please note that.*image.*placeholder.*",
            r"Remember to.*image.*",
            r"Note:.*image.*should.*",
            r"\*\*Note:.*image.*",
        ]
        
        import re
        for pattern in cleanup_patterns:
            markdown = re.sub(pattern, "", markdown, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        # Remove trailing whitespace and multiple blank lines
        markdown = re.sub(r'\n{3,}', '\n\n', markdown.strip())
        
        # Just return the markdown with placeholders - let the frontend generate images
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
        prompt = (
            f"{system_instruction.strip()}\n\n"
            "You are a focused study assistant. Provide clear, concise, and helpful explanations.\n"
            "Rules:\n"
            "- Answer the question directly without meta-commentary\n"
            "- Be educational and accurate\n"
            "- Use examples when helpful\n"
            "- Keep responses concise (2-4 paragraphs max)\n"
            "- DO NOT add notes like 'Please note', 'Remember', or instructions to the user\n\n"
            f"Conversation:\n{conversation}\nUser: {message}\nAssistant:"
        )
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
        
        return response.strip()

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
        
        if json_start != -1:
            return text[json_start:].strip()
        
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
