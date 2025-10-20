"""Utilities for loading and interacting with local AI models."""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from typing import Any, Optional

import torch
from diffusers import AutoPipelineForText2Image
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

try:
    from instructor import Mode, from_hf_pipeline
except Exception:  # pragma: no cover - optional dependency
    Mode = None  # type: ignore[assignment]
    from_hf_pipeline = None  # type: ignore[assignment]

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Container describing generated text."""

    text: str


class ImageGenerationClient:
    """Wrapper around a Diffusers Stable Diffusion pipeline."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.enable_image_generation:
            self._pipeline = None
            self._is_turbo = False
            return

        # Detect if this is a turbo model for optimized generation
        self._is_turbo = "turbo" in self.settings.image_model_id.lower()
        
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        
        # Load VAE separately with proper fp16 variant to avoid dtype mismatch
        vae = None
        if torch.cuda.is_available():
            try:
                from diffusers import AutoencoderKL
                # Use the fp16 fix VAE which properly handles mixed precision
                vae = AutoencoderKL.from_pretrained(
                    "madebyollin/sdxl-vae-fp16-fix",
                    torch_dtype=torch_dtype
                )
            except Exception as e:
                print(f"Warning: Could not load fp16-fix VAE: {e}")
                vae = None
        
        # Use AutoPipeline which automatically selects the right pipeline type
        self._pipeline = AutoPipelineForText2Image.from_pretrained(
            self.settings.image_model_id,
            torch_dtype=torch_dtype,
            safety_checker=None,
            variant="fp16" if torch.cuda.is_available() else None,
            vae=vae,
        )
        
        # SDXL-Turbo requires a specific scheduler for 1-4 step generation
        if self._is_turbo:
            from diffusers import EulerDiscreteScheduler
            # Use EulerDiscreteScheduler instead of EulerAncestralDiscreteScheduler
            # This avoids the index out of bounds error with trailing timesteps
            self._pipeline.scheduler = EulerDiscreteScheduler.from_config(
                self._pipeline.scheduler.config
            )
        
        if torch.cuda.is_available():
            self._pipeline.to("cuda")
            # Enable memory efficient attention to reduce VRAM usage
            self._pipeline.enable_attention_slicing()
        elif torch.backends.mps.is_available():
            self._pipeline.to("mps")
        else:
            self._pipeline.to("cpu")

    def generate(self, prompt: str) -> str:
        if not self.settings.enable_image_generation or self._pipeline is None:
            raise RuntimeError("Image generation is disabled in the current configuration.")

        try:
            # Clear CUDA cache before generation to prevent memory corruption
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            # Generate image with proper parameters based on model type
            if self._is_turbo:
                # SDXL-Turbo: optimized for speed with 1-4 steps, no guidance
                # Use 1 step for fastest generation, no guidance scale
                image = self._pipeline(
                    prompt=prompt,
                    num_inference_steps=1,
                    guidance_scale=0.0,
                ).images[0]
            else:
                # Standard models: use more steps and guidance
                image = self._pipeline(
                    prompt=prompt,
                    num_inference_steps=20,
                    guidance_scale=7.5,
                ).images[0]
            
            # Clear cache after generation
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=90)
            encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return encoded
            
        except Exception as e:
            # On CUDA error, try to recover by clearing cache and resetting
            if torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    # Try to reset CUDA context
                    with torch.cuda.device(0):
                        torch.cuda.empty_cache()
                except:
                    pass
            raise e
