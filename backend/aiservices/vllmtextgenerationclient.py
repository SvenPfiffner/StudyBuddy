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
