from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str

    frontend_url: str = Field(default="http://localhost:3000")

    firebase_credentials_path: str

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
    groq_model: str = "llama-3.2-11b-vision-preview"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "llava"
    ollama_api_key: Optional[str] = None

    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "ap-south-1"
    aws_s3_bucket_name: str
    default_avatar_url: Optional[str] = None

    upload_dir: str = "uploads"

    environment: str = "development"

    public_analyze_daily_limit: int = 5
    schema_auto_create: bool = False

    def ensure_upload_dir(self) -> None:
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_upload_dir()
