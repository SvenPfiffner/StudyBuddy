"""Pydantic models shared by the FastAPI endpoints."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, RootModel


class Flashcard(BaseModel):
    question: str = Field(..., description="Front of the flashcard")
    answer: str = Field(..., description="Back of the flashcard")


class ExamQuestion(BaseModel):
    question: str
    options: List[str]
    correctAnswer: str


class ScriptRequest(BaseModel):
    scriptContent: str = Field(..., description="Concatenated project files")


# ---- RootModel wrappers (v2 way to do `__root__`) ----
class FlashcardResponse(RootModel[List[Flashcard]]):
    pass


class ExamResponse(RootModel[List[ExamQuestion]]):
    pass
# ------------------------------------------------------


class SummaryResponse(BaseModel):
    summary: str


class ChatPart(BaseModel):
    text: str


class ChatMessage(BaseModel):
    role: str
    parts: List[ChatPart]


class ChatRequest(BaseModel):
    history: List[ChatMessage]
    systemInstruction: str
    message: str


class ChatResponse(BaseModel):
    message: str
