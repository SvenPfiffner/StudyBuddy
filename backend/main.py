"""FastAPI entry point exposing the StudyBuddy REST API."""

from __future__ import annotations

import os
os.environ.setdefault("VLLM_WORKER_MULTIPROC_METHOD", "spawn")

import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .config import get_settings
from .schemas import (
    ChatRequest,
    ChatResponse,
    ExamResponse,
    FlashcardResponse,
    ImageRequest,
    ImageResponse,
    ScriptRequest,
    SummaryResponse,
    ProjectRequest,
    GenerateResponse,
)
from .service import StudyBuddyService, get_studybuddy_service

from .storageservice.storageservice import StorageService, get_database_service

logger = logging.getLogger(__name__)

app = FastAPI(title="StudyBuddy Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", summary="Health Check Endpoint")
async def healthcheck():
    settings = get_settings()
    return {
        "status": "ok",
        "textModel": settings.text_model_id,
        "imageModel": settings.image_model_id if settings.enable_image_generation else None,
    }

@app.post("/generate",
          response_model=GenerateResponse,
          summary="Generate content based on a project ID")
async def generate_content(
    payload: ProjectRequest,
    service: StudyBuddyService = Depends(get_studybuddy_service),
):
    pass #TODO: Implement this endpoint


@app.post("/flashcards",
          response_model=FlashcardResponse,
          summary="Get all flashcards for a project")
async def flashcards(
    payload: ProjectRequest,
    service: StorageService = Depends(get_database_service),
):
    document_ids = await run_in_threadpool(service.list_documents, payload.project_id)

    flashcards = []
    for doc_id in document_ids:
        doc_flashcards = await run_in_threadpool(service.list_flashcards, doc_id)
        flashcards.extend(doc_flashcards)
    
    return FlashcardResponse(flashcards)


@app.post("/practice-exam",
          response_model=ExamResponse,
          summary="Get all practice exam questions for a project")
async def practice_exam(
    payload: ProjectRequest,
    service: StorageService = Depends(get_database_service),
):
    document_ids = await run_in_threadpool(service.list_documents, payload.project_id)

    exam_questions = []
    for doc_id in document_ids:
        doc_exam_questions = await run_in_threadpool(service.list_exam_questions, doc_id)
        exam_questions.extend(doc_exam_questions)

    return ExamResponse(exam_questions)


@app.post("/summary-with-images",
          response_model=SummaryResponse,
          summary="Get a summary with images for a project")
async def summary_with_images(
    payload: ProjectRequest,
    service: StorageService = Depends(get_database_service),
):
    # TODO: Get summary with images based on project ID from storageService
    pass


@app.post("/chat",
          response_model=ChatResponse,
          summary="Continue a chat conversation")
async def chat(
    payload: ChatRequest,
    service: StudyBuddyService = Depends(get_studybuddy_service),
):
    try:
        reply = await run_in_threadpool(
            service.continue_chat, payload.history, payload.systemInstruction, payload.message
        )
    except HTTPException:
        raise
    return ChatResponse(message=reply)


__all__ = ["app"]


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
