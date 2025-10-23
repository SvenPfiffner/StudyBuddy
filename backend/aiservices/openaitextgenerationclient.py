# clients/openai_textgenerationclient.py
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass
import json
import os

from pydantic import BaseModel, ValidationError

# OpenAI >= 1.0 SDK
try:
    from openai import OpenAI
except Exception:
    # Fallback to legacy import name if needed
    import openai as _openai_legacy
    OpenAI = None

from ..config import Settings, get_settings
from .textgenerationclient import TextGenerationClient

@dataclass
class GenerationResult:
    text: str


class OpenAITextGenerationClient(TextGenerationClient):
    """
    Works with:
      - api.openai.com (native)
      - Google Gemini OpenAI-compatible endpoint (set base_url)
      - PublicAI / Apertus, vLLM, SGLang, LiteLLM, etc. (set base_url)
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

        # Read creds / endpoint from settings or environment
        api_key = self.settings.external_text_api_key.get_secret_value()
        base_url = self.settings.external_text_api_base_url

        if OpenAI is not None:
            # New SDK - create a custom HTTP client with headers that bypass Cloudflare
            
            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url
            ) if (api_key or base_url) else OpenAI()
            self._sdk = "new"
        else:
            # Legacy SDK fallback (rarely needed today, but safe to include)
            _openai_legacy.api_key = api_key or _openai_legacy.api_key
            if base_url:
                _openai_legacy.base_url = base_url
            self._client = _openai_legacy
            self._sdk = "legacy"

        # Model + default params from your Settings
        self._model = self.settings.external_text_api_id
        self._default_temperature = getattr(self.settings, "temperature", 0.7)
        self._default_max_new_tokens = getattr(self.settings, "max_new_tokens", 256)

    # --- Capability flags -----------------------------------------------------

    @property
    def supports_structured_output(self) -> bool:
        # We validate with Pydantic. Some providers also honor response_format=json_object.
        return True

    # --- Simple text generation ----------------------------------------------

    def generate(
        self,
        prompt: str,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> GenerationResult:
        params = {
            "model": self._model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": self._pick_temp(temperature),
            "max_tokens": self._pick_max(max_new_tokens),
        }

        msg = self._chat_create(params)
        return GenerationResult(text=msg)

    # --- Structured JSON output (schema-validated) ---------------------------

    def generate_structured(
        self,
        prompt: str,
        response_model: Any,  # Pydantic v2 model class
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ):
        """
        Strategy:
          1) Ask for JSON ONLY.
          2) If provider supports OpenAI's JSON mode, set response_format={"type":"json_object"}.
          3) Validate with Pydantic (defensive).
        This works across most OpenAI-compatible servers even if true schema enforcement isn't available.
        """
        # Use a much larger default for structured output (JSON can be verbose)
        default_structured_tokens = 4096
        max_tokens = max_new_tokens if max_new_tokens is not None else default_structured_tokens
        
        params = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are a JSON API. Output ONLY valid JSON with no prose."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0 if temperature is None else temperature,
            "max_tokens": max_tokens,
        }

        # Best effort: many OpenAI-compatible APIs support JSON mode
        # If a provider rejects it, they'll usually ignore it (harmless)
        params["response_format"] = {"type": "json_object"}

        try:
            text = self._chat_create(params)
        except ValueError as e:
            print(f"Structured generation error: {e}")
            raise ValueError(f"Structured generation failed: {e}")

        # Defensive cleanup & validation
        text = text.strip()
        print(f"LLM Response (length={len(text)}): {text[:200]}...")  # Show first 200 chars
        
        if not text:
            raise ValueError("Structured generation failed: Empty response from model")
        
        try:
            return response_model.model_validate_json(text)
        except ValidationError as e:
            print(f"Structured generation failed: {e}")
            # Try to extract JSON if the model wrapped it accidentally
            try:
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1:
                    extracted = text[start : end + 1]
                    print(f"Trying extracted JSON: {extracted[:200]}...")
                    return response_model.model_validate_json(extracted)
            except Exception as extract_error:
                print(f"JSON extraction also failed: {extract_error}")
                pass
            # Re-raise with context
            raise ValueError(f"Structured generation failed: {e}")

    # --- Conversational generation -------------------------------------------

    def generate_conversational(
        self,
        context: str,
        conversation_messages: list[dict],  # [{"role":"user"/"assistant","content":"..."}]
        user_message: str,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> GenerationResult:
        system = (
            "You are StudyBuddy — a playful, warm, witty study coach for novices. "
            "Talk directly to the user in 1–4 sentences; be friendly, concise, and natural. "
            "Use factual claims ONLY from the Context below. If a fact isn’t there, say you’re not sure and (optionally) give a brief guess. "
            "When asked about the source, summarize what it SAYS — do not speculate about where it came from or its type unless the Context states it. "
            "Small talk and curiosity are welcome; answer it briefly. For opinion questions, you don’t have real feelings, "
            "but you may give a light, mascot-style response as long as you don’t present opinions as facts. "
            "Refocus toward studying only if the user asks for study help OR after two consecutive small-talk turns; "
            "when you do, keep the nudge gentle and at most once every few turns. "
            "Avoid quizzes, lists, or multiple options unless requested. English only.\n\n"
            f"Context (authoritative facts):\n{context or ''}"
        )

        messages: list[dict] = [{"role": "system", "content": system}]
        for m in (conversation_messages or []):
            if m.get("role") in {"user", "assistant"} and "content" in m:
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_message})

        params = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.25 if temperature is None else temperature,
            "max_tokens": 120 if max_new_tokens is None else max_new_tokens,
        }

        msg = self._chat_create(params)
        return GenerationResult(text=msg.strip())

    # --- Internals ------------------------------------------------------------

    def _pick_temp(self, t: Optional[float]) -> float:
        return self._default_temperature if t is None else t

    def _pick_max(self, m: Optional[int]) -> int:
        return self._default_max_new_tokens if m is None else m

    def _chat_create(self, params: dict) -> str:
        """
        Wraps both new and legacy OpenAI SDKs, returning the assistant text.
        Expects an OpenAI-compatible chat.completions response.
        """
        if self._sdk == "new":
            # openai>=1.0
            resp = self._client.chat.completions.create(**params)
            # Support text + tool calls fallback to text if needed
            choice = resp.choices[0]
            
            # Check for common error conditions
            if choice.finish_reason == "length":
                usage = getattr(resp, "usage", None)
                tokens_info = f" (prompt={usage.prompt_tokens}, completion={usage.completion_tokens})" if usage else ""
                raise ValueError(
                    f"Model hit token limit. Increase max_tokens (currently {params.get('max_tokens', 'unknown')}){tokens_info}"
                )
            
            if getattr(choice, "message", None):
                # Get content, handle None case
                content = getattr(choice.message, "content", None)
                if content is not None:
                    return content
                # Check for refusal field (some models use this)
                refusal = getattr(choice.message, "refusal", None)
                if refusal:
                    raise ValueError(f"Model refused to generate: {refusal}")
            # If no message or content, raise error instead of returning empty string
            raise ValueError(f"No content in response (finish_reason={choice.finish_reason}): {resp}")
        else:
            # legacy client
            resp = self._client.ChatCompletion.create(**params)  # type: ignore[attr-defined]
            content = resp["choices"][0]["message"].get("content")
            if content is None:
                raise ValueError(f"No content in response: {resp}")
            return content
