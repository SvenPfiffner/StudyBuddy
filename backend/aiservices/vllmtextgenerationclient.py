from typing import Any, Optional
from dataclasses import dataclass
from pydantic import BaseModel

from vllm import LLM, SamplingParams
from vllm.sampling_params import GuidedDecodingParams

from ..config import Settings, get_settings
from .textgenerationclient import TextGenerationClient

@dataclass
class GenerationResult:
    text: str

class VLLMTextGenerationClient(TextGenerationClient):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        # vLLM loads the model once and manages KV cache etc. internally.
        self._llm = LLM(
            model=self.settings.text_model_id,
            dtype="auto",               # pick fp16/bf16 automatically
            kv_cache_dtype="fp8",     # use fp8 for KV cache to save memory
            max_model_len= 8192,      # adjust based on model capabilities (TODO: make configurable)
        )
        # Initialize tokenizer and end-of-turn token for conversational API
        self._tok = self._llm.get_tokenizer()
        self._eot_id = self._tok.convert_tokens_to_ids("<|eot_id|>")

    @property
    def supports_structured_output(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> GenerationResult:
        sp = SamplingParams(
            temperature=temperature if temperature is not None else self.settings.temperature,
            max_tokens=max_new_tokens if max_new_tokens is not None else self.settings.max_new_tokens,
            top_p=0.9 if (temperature or self.settings.temperature) > 0 else 1.0,
            repetition_penalty=1.1,
            stop_token_ids=[],  # add if you need custom stops
        )
        out = self._llm.generate([prompt], sp)[0].outputs[0].text.strip()
        return GenerationResult(text=out)

    def generate_structured(
        self,
        prompt: str,
        response_model: Any,  # expect a Pydantic v2 model
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ):
        schema = response_model.model_json_schema()
        sp = SamplingParams(
            temperature=0.0 if temperature is None else temperature,
            max_tokens=max_new_tokens if max_new_tokens is not None else self.settings.max_new_tokens,
            guided_decoding=GuidedDecodingParams(
                json=schema
            ),
        )
        msg = f"Return ONLY valid JSON for this schema.\n\n{prompt}"
        out = self._llm.generate([msg], sp)[0].outputs[0].text
        # vLLM enforces the schema during decoding; still validate defensively:
        return response_model.model_validate_json(out)
    
    def generate_conversational(
        self,
        context: str,
        conversation_messages: list[dict],  # [{"role":"user"/"assistant","content":"..."}]
        user_message: str,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> GenerationResult:
        # Put policy + authoritative context into SYSTEM so it outranks user text.
        system = (
            "You are StudyBuddy — a playful, warm, witty study coach for novices. "
            "Talk directly to the user in 1–4 sentences; be friendly, concise, and natural. "
            "Use factual claims ONLY from the Context below. If a fact isn’t there, say you’re not sure and (optionally) give a brief guess. "
            "When asked about the source, summarize what it SAYS — do not speculate about where it came from or its type unless the Context states it. "
            "Small talk and curiosity are welcome; answer it briefly. For opinion questions, you don’t have real feelings, "
            "but you may give a light, mascot-style response (e.g., a playful remark) as long as you don’t present opinions as facts. "
            "Refocus toward studying only if the user asks for study help OR after two consecutive small-talk turns; "
            "when you do, keep the nudge gentle and at most once every few turns. "
            "Avoid quizzes, lists, or multiple options unless requested. English only.\n\n"
            f"Context (authoritative facts):\n{context or ''}"
        )


        messages = [{"role": "system", "content": system}]
        # include the last few turns if you have them
        for m in (conversation_messages or []):
            # ensure only "user" / "assistant" roles go here
            if m.get("role") in {"user", "assistant"} and "content" in m:
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": user_message})

        # Use the model’s native chat template
        prompt = self._tok.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,  # appends assistant header; model will end with <|eot_id|>
        )

        sp = SamplingParams(
            temperature=0.25 if temperature is None else temperature,  # calmer
            max_tokens=120 if max_new_tokens is None else max_new_tokens,
            top_p=0.9,
            repetition_penalty=1.08,
            stop_token_ids=[self._eot_id],  # stop at end-of-turn
        )

        out = self._llm.generate([prompt], sp)[0].outputs[0].text
        # vLLM returns only the completion after the assistant header, but be safe:
        cleaned = out.split("<|eot_id|>")[0].strip()
        return GenerationResult(text=cleaned)
