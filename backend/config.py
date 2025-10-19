from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the StudyBuddy backend."""

    text_model_id: str = Field(
        default="meta-llama/Llama-3.1-8B-Instruct",
        description="Hugging Face model id used for text generation.",
    )
    image_model_id: str = Field(
        default="stabilityai/sdxl-turbo",
        description="Diffusers checkpoint id used for image generation.",
    )
    max_new_tokens: int = Field(
        default=1024,
        description="Maximum number of tokens to generate for a single request.",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature applied to the LLM.",
    )
    enable_image_generation: bool = Field(
        default=True,
        description="Disable to skip image creation while still returning a textual summary.",
    )

    # ✅ Pydantic v2 replacement for class Config
    model_config = SettingsConfigDict(
        env_prefix="STUDYBUDDY_",
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
