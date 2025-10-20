from typing import Any, Optional
import logging
from dataclasses import dataclass

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

from .textgenerationclient import TextGenerationClient
from ..config import Settings, get_settings

logger = logging.getLogger(__name__)

@dataclass
class GenerationResult:
    """Container describing generated text."""

    text: str

class LocalTextGenerationClient(TextGenerationClient):

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._tokenizer = AutoTokenizer.from_pretrained(self.settings.text_model_id)
        
        # Use 4-bit quantization to reduce VRAM usage
        # This reduces memory by ~75% with minimal quality loss
        if torch.cuda.is_available():
            from transformers import BitsAndBytesConfig
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
            self._model = AutoModelForCausalLM.from_pretrained(
                self.settings.text_model_id,
                quantization_config=quantization_config,
                device_map="auto",
                low_cpu_mem_usage=True,
            )
        elif torch.backends.mps.is_available():
            # MPS (Apple Silicon)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.settings.text_model_id,
                torch_dtype=torch.float16,
                device_map={"": torch.device("mps")},
                low_cpu_mem_usage=True,
            )
        else:
            # CPU fallback - no quantization
            self._model = AutoModelForCausalLM.from_pretrained(
                self.settings.text_model_id,
                torch_dtype=torch.float32,
                device_map="cpu",
                low_cpu_mem_usage=True,
            )
        
        self._pipeline = pipeline(
            "text-generation",
            model=self._model,
            tokenizer=self._tokenizer,
            return_full_text=False,
        )

        # Some models (e.g. Mistral) lack an explicit pad token, so align with EOS.
        if self._pipeline.tokenizer.pad_token_id is None:
            self._pipeline.tokenizer.pad_token_id = self._pipeline.tokenizer.eos_token_id

    @property
    def supports_structured_output(self) -> bool:
        return False

    def generate(
        self,
        prompt: str,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        settings = self.settings
        temperature = temperature if temperature is not None else settings.temperature
        max_new_tokens = max_new_tokens if max_new_tokens is not None else settings.max_new_tokens

        do_sample = temperature > 0
        outputs = self._pipeline(
            prompt,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            temperature=temperature if do_sample else None,
            top_p=0.9 if do_sample else None,
            repetition_penalty=1.1,  # Prevent repetitive text
            eos_token_id=self._pipeline.tokenizer.eos_token_id,
        )
        text = outputs[0]["generated_text"].strip()
        return GenerationResult(text=text)

    def generate_structured(
        self,
        prompt: str,
        response_model: Any,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        
        raise RuntimeError("Structured generation is not available with the local text generation client.")