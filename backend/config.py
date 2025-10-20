from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the StudyBuddy backend."""

    #----------------------------------------------------------
    # External API settings
    #----------------------------------------------------------
    use_external_text_api: bool = Field(
        default=False,
        description="If true, use an external API for text generation instead of local models.",
    )

    external_text_api_id: str = Field(
        default="your-external-api-id",
        description="Identifier for the external text generation API.",
    )

    external_text_api_key: SecretStr = Field(
        default="",
        description="API key for authenticating with the external text generation service.",
    )

    use_external_image_api: bool = Field(
        default=False,
        description="If true, use an external API for image generation instead of local models.",
    )

    external_image_api_id: str = Field(
        default="your-external-image-api-id",
        description="Identifier for the external image generation API.",
    )

    external_image_api_key: SecretStr = Field(
        default="",
        description="API key for authenticating with the external image generation service.",
    )

    #----------------------------------------------------------
    # Local model settings
    #----------------------------------------------------------
    text_model_id: str = Field(
        default="meta-llama/Llama-3.1-8B-Instruct",
        description="Hugging Face model id used for text generation.",
    )
    image_model_id: str = Field(
        default="stabilityai/sdxl-turbo",
        description="Diffusers checkpoint id used for image generation.",
    )

    #----------------------------------------------------------
    # Generation settings
    #----------------------------------------------------------
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
