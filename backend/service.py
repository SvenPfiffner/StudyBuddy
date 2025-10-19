"""Domain logic for converting StudyBuddy requests into LLM prompts."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from textwrap import dedent
from typing import Any, List

from fastapi import HTTPException, status

from .config import Settings, get_settings
from .llm import GenerationResult, ImageGenerationClient, TextGenerationClient
from .schemas import (
    ChatMessage,
    ExamQuestion,
    ExamResponse,
    Flashcard,
    FlashcardResponse,
)

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
        prompt = dedent(
            f"""\
            You are StudyBuddy, an educational assistant who distills material into flashcards students can memorize quickly.

            The study material is delimited by <<<STUDY_MATERIAL>>> markers. Produce concise, self-contained flashcards that cover:
            - Core definitions and facts students must memorize.
            - Key processes or cause-effect relationships.
            - Comparisons or contrasts that clarify concepts.

            Quality guidelines:
            - Keep questions to a single sentence phrased as prompts (avoid yes/no).
            - Answers should be specific and limited to 1-3 sentences.
            - Avoid repeating the same fact across multiple cards.
            - Favor factual precision over creative wording.
            - Aim for 8-12 high-quality flashcards; prioritize breadth if the material allows.

            <<<STUDY_MATERIAL>>>
            {script_content.strip()}
            <<<END_STUDY_MATERIAL>>>

            Respond by filling the JSON schema (list of flashcards with 'question' and 'answer' fields) with no supplementary prose."""
        )
        structured = self._maybe_generate_structured(
            prompt,
            FlashcardResponse,
            max_new_tokens=768,
        )
        if structured is not None:
            try:
                if isinstance(structured, FlashcardResponse):
                    return list(structured.root)
                if isinstance(structured, list):
                    return [Flashcard.model_validate(item) for item in structured]
                return list(FlashcardResponse.model_validate(structured).root)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to interpret structured flashcards: %s", exc)
        result = self._safe_generate(prompt, max_new_tokens=768)
        return self._parse_json_array(result.text, Flashcard)

    # ------------------------------------------------------------------
    # Practice Exam
    # ------------------------------------------------------------------
    def generate_practice_exam(self, script_content: str) -> List[ExamQuestion]:
        prompt = dedent(
            f"""\
            You are StudyBuddy, a teacher crafting a multiple-choice practice exam from the provided material.

            Study material is wrapped in <<<STUDY_MATERIAL>>> markers. Your task is to design exam questions that:
            - Target distinct, high-value concepts students must master.
            - Challenge common misconceptions with realistic distractors.
            - Use clear, direct language without rhetorical fluff.

            Quality guidelines:
            - Write 5-7 questions that can be answered using the study material alone.
            - Ensure each set of four options are mutually exclusive and similar in length.
            - The correct answer should be the only fully accurate statement; others should contain a specific flaw.
            - Copy the correct answer exactly into the 'correctAnswer' field.

            <<<STUDY_MATERIAL>>>
            {script_content.strip()}
            <<<END_STUDY_MATERIAL>>>

            Respond by filling the JSON schema (list of questions with 'question', 'options', and 'correctAnswer') with no extra commentary."""
        )
        structured = self._maybe_generate_structured(
            prompt,
            ExamResponse,
            max_new_tokens=1024,
        )
        if structured is not None:
            try:
                if isinstance(structured, ExamResponse):
                    questions = list(structured.root)
                elif isinstance(structured, list):
                    questions = [ExamQuestion.model_validate(item) for item in structured]
                else:
                    questions = list(ExamResponse.model_validate(structured).root)
                return self._validate_exam_questions(questions)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to interpret structured exam output: %s", exc)
        result = self._safe_generate(prompt, max_new_tokens=1024)
        questions = self._parse_json_array(result.text, ExamQuestion)
        return self._validate_exam_questions(questions)

    # ------------------------------------------------------------------
    # Summary + images
    # ------------------------------------------------------------------
    def generate_summary_with_images(self, script_content: str) -> str:
        prompt = dedent(
            f"""\
            You are StudyBuddy, an expert educator who writes structured study guides with vivid illustrative imagery.

            Study material appears between <<<STUDY_MATERIAL>>> markers.

            Process:
            1. Skim the material and determine 3-4 learning objectives (keep them to yourself).
            2. Expand the objectives into a 400-600 word Markdown summary using the format below.
            3. Verify the checklist before finalizing your response.

            Mandatory Markdown format:
            ## Introduction
            [content]

            [IMAGE_PROMPT: detailed description]

            ## Main Section
            [content]

            [IMAGE_PROMPT: detailed description]

            ## Conclusion
            [content]

            [IMAGE_PROMPT: detailed description]

            Illustration guidance:
            - Describe dynamic scenes or naturalistic illustrations that communicate the concept without on-image text.
            - Highlight concrete visual elements (setting, objects, colors, motion, lighting).
            - Avoid infographic styles, labels, or word art; let the composition convey meaning visually.
            - Example: [IMAGE_PROMPT: A cross-section illustration of a leaf showing water rising through bright blue xylem vessels while morning light streams across the canopy]

            Checklist:
            - Exactly 3 lines begin with [IMAGE_PROMPT: and each follows the guidance above.
            - Total word count between 400 and 600.
            - No dialogue tags, meta-commentary, or instructions to the user.
            - Sentences are complete and well-formed.

            <<<STUDY_MATERIAL>>>
            {script_content.strip()}
            <<<END_STUDY_MATERIAL>>>

            Summary:"""
        )
        result = self._safe_generate(prompt, max_new_tokens=768)
        markdown = result.text
        
        # Aggressive cleanup of hallucinations
        import re
        
        # Remove everything after common hallucination patterns
        stop_patterns = [
            r'---+\s*Human:',
            r'---+\s*Revised',
            r'---+\s*\*\*Revised',
            r'Human:\s*',
            r'Assistant:\s*',
            r'Revised\s+Introduction',
            r'Can you rephrase',
        ]
        
        for pattern in stop_patterns:
            match = re.search(pattern, markdown, re.IGNORECASE)
            if match:
                markdown = markdown[:match.start()]
                break
        
        # Remove trailing incomplete sentences
        markdown = markdown.strip()
        if markdown and not markdown[-1] in '.!?)':
            # Find last complete sentence
            last_period = max(
                markdown.rfind('. '),
                markdown.rfind('.\n'),
                markdown.rfind('!\n'),
                markdown.rfind('?\n')
            )
            if last_period > 0:
                markdown = markdown[:last_period + 1]
        
        # Remove meta-commentary
        cleanup_patterns = [
            r'Please note.*?(?:\.|$)',
            r'Remember.*?(?:\.|$)',
            r'Note:.*?(?:\.|$)',
            r'\*\*Note:.*?(?:\.|$)',
        ]
        
        for pattern in cleanup_patterns:
            markdown = re.sub(pattern, "", markdown, flags=re.IGNORECASE)
        
        # Clean up whitespace
        markdown = re.sub(r'\n{3,}', '\n\n', markdown.strip())
        
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
        prompt = dedent(
            f"""{system_instruction.strip()}

            You are StudyBuddy, a focused tutor who responds with clear, evidence-based explanations grounded in the conversation history.

            Instructions:
            - Provide the best possible answer to the latest user question.
            - If key information is missing, ask the user to clarify instead of guessing.
            - Use concrete examples when they improve understanding.
            - Keep the reply within four short paragraphs or fewer.
            - Do not include meta-commentary such as "Please note" or system-level reminders.
            - When referencing earlier turns, quote short phrases from the conversation in quotation marks.
            - Silently reflect on the user's intent before responding, but do not reveal that reflection.

            Conversation so far:
            {conversation}

            User: {message}
            Assistant:"""
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

    def _validate_exam_questions(self, questions: List[ExamQuestion]) -> List[ExamQuestion]:
        for idx, question in enumerate(questions):
            if len(question.options) != 4:
                logger.error(
                    "Question %d has %d options instead of 4: %s",
                    idx,
                    len(question.options),
                    question.options,
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Generated exam question {idx+1} does not have exactly four options (has {len(question.options)}).",
                )

            if question.correctAnswer not in question.options:
                matched_option = None
                correct_lower = question.correctAnswer.lower()
                for option in question.options:
                    option_lower = option.lower()
                    if correct_lower in option_lower or option_lower in correct_lower:
                        matched_option = option
                        break

                if matched_option:
                    logger.warning(
                        "Question %d: Fuzzy matched correctAnswer '%s' to option '%s'",
                        idx,
                        question.correctAnswer,
                        matched_option,
                    )
                    question.correctAnswer = matched_option
                else:
                    logger.error(
                        "Question %d correctAnswer '%s' not in options: %s",
                        idx,
                        question.correctAnswer,
                        question.options,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Generated exam question {idx+1} has a correctAnswer that is not one of the options.",
                    )
        return questions

    def _maybe_generate_structured(self, prompt: str, response_model: Any, max_new_tokens: int):
        if not self._text_client.supports_structured_output:
            return None
        try:
            return self._text_client.generate_structured(
                prompt=prompt,
                response_model=response_model,
                max_new_tokens=max_new_tokens,
            )
        except Exception as exc:
            logger.warning("Structured generation failed: %s", exc)
            return None

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
