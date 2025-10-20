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
from .llm import ImageGenerationClient
from .aiservices.localtextgenerationclient import GenerationResult, LocalTextGenerationClient
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
        self._text_client = LocalTextGenerationClient(self.settings)
        self._image_client = ImageGenerationClient(self.settings)

    # ------------------------------------------------------------------
    # Flashcards
    # ------------------------------------------------------------------
    def generate_flashcards(self, script_content: str) -> List[Flashcard]:
        prompt = dedent(
            f"""\
            Generate a JSON array of 8-12 flashcards from the study material below.

            CRITICAL OUTPUT REQUIREMENTS:
            - Output ONLY a valid JSON array. Start with [ and end with ]
            - Do NOT include any explanatory text before or after the JSON
            - Do NOT include markdown code fences (```)
            - Do NOT include phrases like "Here is" or "Please complete"
            - Your entire response must be parseable as JSON

            Each flashcard object must have:
            - "question": A single sentence prompt (not yes/no question)
            - "answer": A specific answer in 1-3 sentences

            Quality guidelines:
            - Cover core definitions, facts, processes, and relationships
            - Make each card self-contained and memorizable
            - Avoid repeating information across cards
            - Prioritize factual precision over creative wording

            <<<STUDY_MATERIAL>>>
            {script_content.strip()}
            <<<END_STUDY_MATERIAL>>>

            JSON array:"""
        )
        structured = self._maybe_generate_structured(
            prompt,
            list[Flashcard],
            max_new_tokens=768,
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
            max_new_tokens=768,
        )

    # ------------------------------------------------------------------
    # Practice Exam
    # ------------------------------------------------------------------
    def generate_practice_exam(self, script_content: str) -> List[ExamQuestion]:
        prompt = dedent(
            f"""\
            Generate a JSON array of 5-7 multiple-choice exam questions based on the study material below.

            CRITICAL OUTPUT REQUIREMENTS:
            - Output ONLY a valid JSON array. Start with [ and end with ]
            - Do NOT include any explanatory text before or after the JSON
            - Do NOT include markdown code fences (```)
            - Do NOT include phrases like "Here is" or "Please fill out"
            - Your entire response must be parseable as JSON

            Each question object must have:
            - "question": A clear, direct question (one sentence)
            - "options": An array of exactly 4 answer choices (strings)
            - "correctAnswer": The exact text of one of the options

            Quality guidelines:
            - Target distinct, high-value concepts from the material
            - Make options mutually exclusive and similar in length
            - Only the correct answer should be fully accurate
            - Create realistic distractors based on common misconceptions

            <<<STUDY_MATERIAL>>>
            {script_content.strip()}
            <<<END_STUDY_MATERIAL>>>

            JSON array:"""
        )
        structured = self._maybe_generate_structured(
            prompt,
            list[ExamQuestion],
            max_new_tokens=1024,
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
                return self._validate_exam_questions(questions)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to interpret structured exam output: %s", exc)
        questions = self._generate_json_with_retry(
            prompt,
            ExamQuestion,
            max_new_tokens=1024,
        )
        return self._validate_exam_questions(questions)

    # ------------------------------------------------------------------
    # Summary + images
    # ------------------------------------------------------------------
    def generate_summary_with_images(self, script_content: str) -> str:
        prompt = dedent(
            f"""\
            Create a study guide summary following this EXACT structure. Do not deviate from this format.

            MANDATORY FORMAT - Copy this structure exactly:

            ## Introduction
            [Write 1-2 paragraphs here introducing the main topic and why it matters]

            [IMAGE_PROMPT: Describe a vivid illustration scene here with concrete visual details]

            ## Key Concepts
            [Write 2-3 paragraphs here explaining the main ideas, processes, or mechanisms]

            [IMAGE_PROMPT: Describe another illustration showing the concepts in action]

            ## Summary
            [Write 1-2 paragraphs here summarizing the key takeaways]

            [IMAGE_PROMPT: Describe a final illustration that reinforces the main message]

            CRITICAL RULES:
            1. Start with "## Introduction" exactly as shown
            2. After introduction paragraphs, add ONE line: [IMAGE_PROMPT: description]
            3. Then add "## Key Concepts" section with paragraphs
            4. After key concepts, add ONE line: [IMAGE_PROMPT: description]
            5. Then add "## Summary" section with paragraphs
            6. After summary, add ONE line: [IMAGE_PROMPT: description]
            7. Do NOT use markdown image syntax like ![text](url)
            8. Do NOT skip sections or change section names
            9. IMAGE_PROMPT descriptions should be SHORT (20-40 words maximum)
            
            IMAGE PROMPT RULES - READ CAREFULLY:
            - Create SYMBOLIC or CONCEPTUAL scenes, NOT technical diagrams
            - NO charts, graphs, flowcharts, circuit diagrams, protocol diagrams, or network diagrams
            - NO text, labels, arrows, or annotations in the image
            - Think like stock photography: what OBJECTS, SCENES, or METAPHORS represent this concept?
            - Use concrete objects: locks, keys, doors, hands, books, light, nature, architecture
            - Focus on: lighting, mood, composition, realistic objects, symbolic representation
            
            GOOD examples (symbolic/conceptual):
            [IMAGE_PROMPT: A glowing padlock surrounded by floating digital keys in a dark blue environment, symbolizing encryption and security]
            [IMAGE_PROMPT: Two hands exchanging a sealed envelope with a wax stamp, representing secure message transfer, warm lighting]
            [IMAGE_PROMPT: A fortress gate with intricate lock mechanisms, symbolizing authentication, dramatic sunset lighting]
            
            BAD examples (too technical - avoid these):
            ❌ A flowchart showing client-server handshake protocol
            ❌ A diagram with arrows connecting nodes
            ❌ A cryptographic algorithm visualization with equations
            ❌ A network topology diagram

            <<<STUDY_MATERIAL>>>
            {script_content.strip()}
            <<<END_STUDY_MATERIAL>>>

            Now write the study guide following the exact format above:

            ## Introduction"""
        )
        # Use lower temperature for more consistent formatting
        result = self._safe_generate(prompt, max_new_tokens=768, temperature=0.3)
        markdown = result.text
        
        # If the model didn't include the ## Introduction prefix, add it back
        if not markdown.strip().startswith("##"):
            markdown = "## Introduction\n" + markdown
        
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
        
        # Clean up markdown image syntax that the model might hallucinate
        # Convert ![alt text](url) to a generic IMAGE_PROMPT if found
        markdown_image_pattern = r'!\[([^\]]*)\]\([^\)]+\)'
        def replace_markdown_image(match):
            alt_text = match.group(1)
            # Try to extract a meaningful description from the alt text
            if alt_text and len(alt_text) > 10:
                logger.warning(f"Found markdown image syntax, converting to IMAGE_PROMPT: {alt_text}")
                return f"[IMAGE_PROMPT: {alt_text}]"
            else:
                # If alt text is empty or too short, create a generic prompt
                logger.warning("Found markdown image with poor alt text, using generic prompt")
                return "[IMAGE_PROMPT: An illustration related to the study material]"
        
        markdown = re.sub(markdown_image_pattern, replace_markdown_image, markdown)
        
        # Clean up technical diagram language from image prompts
        def cleanup_image_prompt(match):
            prompt = match.group(1)
            original = prompt
            
            # Remove technical diagram indicators
            technical_terms = [
                'diagram', 'flowchart', 'chart', 'graph', 'illustration showing',
                'network topology', 'protocol flow', 'algorithm', 'visualization',
                'arrows', 'boxes', 'nodes', 'edges', 'labeled', 'annotated',
                'step-by-step', 'sequence diagram'
            ]
            
            # Check if prompt is too technical
            prompt_lower = prompt.lower()
            is_technical = any(term in prompt_lower for term in technical_terms)
            
            if is_technical:
                # Try to extract the core concept and make it symbolic
                # This is a simple heuristic - just warn and keep for now
                logger.warning(f"Potentially technical image prompt detected: {prompt[:50]}...")
            
            # Trim if too long (SDXL works best with shorter prompts)
            if len(prompt) > 200:
                prompt = prompt[:200].rsplit(',', 1)[0]  # Cut at last comma
                logger.info(f"Trimmed long image prompt from {len(original)} to {len(prompt)} chars")
            
            return f"[IMAGE_PROMPT: {prompt}]"
        
        markdown = re.sub(IMAGE_PROMPT_REGEX, cleanup_image_prompt, markdown)
        
        # Re-extract after cleanup
        # Validate that we have IMAGE_PROMPT tags and proper structure
        image_prompts = IMAGE_PROMPT_REGEX.findall(markdown)
        has_sections = bool(re.search(r'##\s+(Introduction|Key Concepts|Summary)', markdown))
        
        # If format is completely wrong, try one more time with even stricter prompt
        if len(image_prompts) == 0 or not has_sections:
            logger.warning(f"Summary format incorrect (prompts: {len(image_prompts)}, sections: {has_sections}). Retrying with stricter prompt.")
            
            retry_prompt = dedent(
                f"""\
                You must follow this EXACT template. Fill in the [CONTENT] sections with your text.

                ## Introduction
                [CONTENT: Write 1-2 paragraphs introducing the topic]

                [IMAGE_PROMPT: A SHORT symbolic scene (20-40 words) using CONCRETE OBJECTS - NO diagrams, charts, or technical visualizations. Think stock photography with objects like locks, keys, books, nature, light]

                ## Key Concepts
                [CONTENT: Write 2-3 paragraphs explaining the main ideas]

                [IMAGE_PROMPT: Another SHORT symbolic scene (20-40 words) representing the concept metaphorically with REAL OBJECTS and dramatic lighting]

                ## Summary
                [CONTENT: Write 1-2 paragraphs summarizing key points]

                [IMAGE_PROMPT: A final SHORT symbolic scene (20-40 words) using CONCRETE OBJECTS to represent the main message]

                DO NOT:
                - Skip any sections
                - Use ![image](url) syntax
                - Write single-paragraph summaries
                - Omit the [IMAGE_PROMPT: lines

                Study material:
                {script_content.strip()[:500]}...

                Now generate following the template exactly:

                ## Introduction"""
            )
            
            retry_result = self._safe_generate(retry_prompt, max_new_tokens=768, temperature=0.1)
            retry_markdown = retry_result.text
            
            if not retry_markdown.strip().startswith("##"):
                retry_markdown = "## Introduction\n" + retry_markdown
            
            # Check if retry is better
            retry_image_prompts = IMAGE_PROMPT_REGEX.findall(retry_markdown)
            retry_has_sections = bool(re.search(r'##\s+(Introduction|Key Concepts|Summary)', retry_markdown))
            
            if len(retry_image_prompts) > len(image_prompts) or (retry_has_sections and not has_sections):
                logger.info(f"Retry improved format: {len(retry_image_prompts)} prompts, sections: {retry_has_sections}")
                markdown = retry_markdown
                image_prompts = retry_image_prompts
            else:
                logger.warning("Retry did not improve format, using original")
        
        if len(image_prompts) == 0:
            logger.warning("No IMAGE_PROMPT tags found in generated summary. Model may have ignored instructions.")
        elif len(image_prompts) < 3:
            logger.warning(f"Only {len(image_prompts)} IMAGE_PROMPT tags found (expected 3)")
        
        # Fix markdown formatting: Remove ALL indentation and ensure proper spacing
        # Indented lines (4+ spaces) are treated as code blocks in markdown
        lines = markdown.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            # Strip leading whitespace from ALL non-empty lines
            # The model often adds indentation which breaks markdown
            if line.strip():
                cleaned_line = line.strip()
                
                # Check if this is an IMAGE_PROMPT line
                if cleaned_line.startswith('[IMAGE_PROMPT:'):
                    # Ensure blank line before (if not already)
                    if fixed_lines and fixed_lines[-1].strip():
                        fixed_lines.append('')
                    fixed_lines.append(cleaned_line)
                    # Ensure blank line after
                    if i + 1 < len(lines) and lines[i + 1].strip():
                        fixed_lines.append('')
                # Check if this is a header
                elif cleaned_line.startswith('##'):
                    # Ensure blank line before header (if not already and not first line)
                    if fixed_lines and fixed_lines[-1].strip():
                        fixed_lines.append('')
                    fixed_lines.append(cleaned_line)
                    # No extra line after headers
                else:
                    # Regular content line - just strip the indentation
                    fixed_lines.append(cleaned_line)
            else:
                # Preserve empty lines
                fixed_lines.append('')
        
        markdown = '\n'.join(fixed_lines)
        
        # Clean up excessive whitespace (more than 2 blank lines)
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
        
        response = self._strip_hallucinated_turns(response)
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
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
