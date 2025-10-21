"""Pydantic models shared by the FastAPI endpoints."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, RootModel


class Flashcard(BaseModel):
    question: str = Field(..., description="Front of the flashcard")
    answer: str = Field(..., description="Back of the flashcard")

class FlashcardList(BaseModel):
    flashcards: List[Flashcard] = Field(..., description="List of flashcards")

class ExamQuestion(BaseModel):
    question: str
    options: List[str]
    correctAnswer: str

class ExamQuestionList(BaseModel):
    questions: List[ExamQuestion] = Field(..., description="List of exam questions")


class ScriptRequest(BaseModel):
    scriptContent: str = Field(..., description="Concatenated project files")

class Project(BaseModel):
    name: str = Field(..., description="Name of the project")
    summary: str = Field(..., description="Summary of the project")


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


class ImageRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt for image generation")


class ImageResponse(BaseModel):
    image: str = Field(..., description="Base64-encoded JPEG image")

class ProjectRequest(BaseModel):
    project_id: int = Field(..., description="ID of the project to consider in this request.")

class GenerateResponse(BaseModel):
    status: str = Field(..., description="Status of the generation request")

class AddDocumentRequest(BaseModel):
    project_id: int = Field(..., description="ID of the project to add the document to")
    title: str = Field(..., description="Title of the document")
    content: str = Field(..., description="Content of the document")

class AddDocumentResponse(BaseModel):
    document_id: int = Field(..., description="ID of the created document")
    message: str = Field(..., description="Success message")
