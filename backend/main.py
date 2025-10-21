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
)
from .service import StudyBuddyService, get_service

logger = logging.getLogger(__name__)

app = FastAPI(title="StudyBuddy Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def healthcheck():
    settings = get_settings()
    return {
        "status": "ok",
        "textModel": settings.text_model_id,
        "imageModel": settings.image_model_id if settings.enable_image_generation else None,
    }


@app.post("/flashcards", response_model=FlashcardResponse)
async def flashcards(
    payload: ScriptRequest,
    service: StudyBuddyService = Depends(get_service),
):
    items = await run_in_threadpool(service.generate_flashcards, payload.scriptContent)
    return items


@app.post("/practice-exam", response_model=ExamResponse)
async def practice_exam(
    payload: ScriptRequest,
    service: StudyBuddyService = Depends(get_service),
):
    questions = await run_in_threadpool(service.generate_practice_exam, payload.scriptContent)

    return questions


@app.post("/summary-with-images", response_model=SummaryResponse)
async def summary_with_images(
    payload: ScriptRequest,
    service: StudyBuddyService = Depends(get_service),
):
    summary = await run_in_threadpool(service.generate_summary_with_images, payload.scriptContent)

    return SummaryResponse(summary=summary)


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: StudyBuddyService = Depends(get_service),
):
    try:
        reply = await run_in_threadpool(
            service.continue_chat, payload.history, payload.systemInstruction, payload.message
        )
    except HTTPException:
        raise
    return ChatResponse(message=reply)


@app.post("/generate-image", response_model=ImageResponse)
async def generate_image(
    payload: ImageRequest,
    service: StudyBuddyService = Depends(get_service),
):
    image_b64 = await run_in_threadpool(service.generate_image, payload.prompt)

    return ImageResponse(image=image_b64)


__all__ = ["app"]


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
