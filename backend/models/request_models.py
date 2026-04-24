from pydantic import BaseModel, Field, field_validator

from backend.config import MAX_QUERY_CHARS


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_CHARS)
    user_id: str | None = Field(default=None, max_length=128)
    language: str = Field(default="hi-IN", min_length=2, max_length=16)
    profile: dict | None = None
    include_plan: bool = Field(default=False)

    @field_validator("query")
    @classmethod
    def _query_not_blank(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("query must not be blank")
        return cleaned


class VapiWebhookRequest(BaseModel):
    message: dict
