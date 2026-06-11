from pydantic import BaseModel, Field


class Citation(BaseModel):
    id: int
    source: str
    section: str
    excerpt: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    grounded: bool


class DocumentInfo(BaseModel):
    source: str
    chunks: int
