"""Utilities for loading and interacting with local AI models."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Optional

import torch
from diffusers import StableDiffusionPipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

from .config import Settings, get_settings


@dataclass
class GenerationResult:
    """Container describing generated text."""

    text: str


class TextGenerationClient:
    """Wrapper around a Hugging Face causal language model."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._tokenizer = AutoTokenizer.from_pretrained(self.settings.text_model_id)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.settings.text_model_id,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
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

    def generate(self, prompt: str, max_new_tokens: Optional[int] = None, temperature: Optional[float] = None) -> GenerationResult:
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
            eos_token_id=self._pipeline.tokenizer.eos_token_id,
        )
        text = outputs[0]["generated_text"].strip()
        return GenerationResult(text=text)


class ImageGenerationClient:
    """Wrapper around a Diffusers Stable Diffusion pipeline."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.enable_image_generation:
            self._pipeline = None
            return

        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self._pipeline = StableDiffusionPipeline.from_pretrained(
            self.settings.image_model_id,
            torch_dtype=torch_dtype,
            safety_checker=None,
        )
        if torch.cuda.is_available():
            self._pipeline.to("cuda")
        else:
            self._pipeline.to("cpu")

    def generate(self, prompt: str) -> str:
        if not self.settings.enable_image_generation or self._pipeline is None:
            raise RuntimeError("Image generation is disabled in the current configuration.")

        if torch.cuda.is_available():
            with torch.autocast("cuda"):
                image = self._pipeline(prompt).images[0]
        else:
            image = self._pipeline(prompt).images[0]
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return encoded
