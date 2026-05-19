from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str

    frontend_url: str = Field(default="http://localhost:3000")

    jwt_secret_key: str = Field(
        min_length=16,
        description="HS256 signing secret for JWT access tokens",
    )

    jwt_access_token_expire_minutes: int = Field(
        default=60 * 24 * 7,
        ge=5,
        le=60 * 24 * 365,
        description="Access token lifetime in minutes",
    )

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def strip_jwt_secret(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    # Base URL for ``file_url`` / ``/media/...`` links (e.g. http://127.0.0.1:8000 or LAN IP for mobile).
    public_media_base_url: str = "http://127.0.0.1:8000"

    llm_provider: str = Field(
        default="gemini",
        description="gemini | openai | groq | bedrock | ollama",
    )

    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"

    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    groq_api_key: Optional[str] = None
    groq_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "llava"
    ollama_api_key: Optional[str] = None

    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "ap-south-1"
    default_avatar_url: Optional[str] = None

    upload_dir: str = "uploads"

    environment: str = "development"

    public_analyze_daily_limit: int = 5
    schema_auto_create: bool = False

    def ensure_upload_dir(self) -> None:
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_upload_dir()
