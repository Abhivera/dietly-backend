from pydantic import BaseModel, Field


class SessionBody(BaseModel):
    full_name: str | None = Field(None, max_length=100)
