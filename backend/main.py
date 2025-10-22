"""FastAPI entry point exposing the StudyBuddy REST API."""

from __future__ import annotations

import os
os.environ.setdefault("VLLM_WORKER_MULTIPROC_METHOD", "spawn")

import logging
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .config import get_settings
from .schemas import (
    AddDocumentRequest,
    AddDocumentResponse,
    ChatRequest,
    ChatResponse,
    CreateProjectRequest,
    CreateProjectResponse,
    DeleteResponse,
    DocumentItem,
    DocumentListResponse,
    EnsureUserRequest,
    EnsureUserResponse,
    ExamResponse,
    FlashcardResponse,
    GenerateResponse,
    ImageRequest,
    ImageResponse,
    ProjectListItem,
    ProjectListResponse,
    ProjectRequest,
    SummaryResponse,
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


@app.post(
    "/ensure_user",
    response_model=EnsureUserResponse,
    summary="Ensure a user exists and return the user id",
)
async def ensure_user(
    payload: EnsureUserRequest,
    service: StorageService = Depends(get_database_service),
):
    user_id = await run_in_threadpool(service.get_or_create_user, payload.name)
    return EnsureUserResponse(user_id=user_id)


@app.get(
    "/users/{user_id}/projects",
    response_model=ProjectListResponse,
    summary="List all projects for a user",
)
async def list_projects(
    user_id: int,
    service: StorageService = Depends(get_database_service),
):
    rows = await run_in_threadpool(service.list_projects, user_id)
    projects: List[ProjectListItem] = []
    for row in rows:
        document_ids = await run_in_threadpool(service.list_documents, row["id"])
        projects.append(
            ProjectListItem(
                id=row["id"],
                name=row["name"],
                summary=row["summary"],
                document_count=len(document_ids),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )

    return ProjectListResponse(projects=projects)


@app.delete(
    "/projects/{project_id}",
    response_model=DeleteResponse,
    summary="Delete a project and its related data",
)
async def delete_project(
    project_id: int,
    service: StorageService = Depends(get_database_service),
):
    await run_in_threadpool(service.delete_project, project_id)
    return DeleteResponse(status="success", message=f"Project {project_id} deleted")


@app.get(
    "/projects/{project_id}/documents",
    response_model=DocumentListResponse,
    summary="List documents for a project",
)
async def list_documents(
    project_id: int,
    include_content: bool = False,
    service: StorageService = Depends(get_database_service),
):
    if include_content:
        rows = await run_in_threadpool(service.list_documents_with_content, project_id)
    else:
        rows = await run_in_threadpool(service.list_documents_with_metadata, project_id)

    documents: List[DocumentItem] = []
    for row in rows:
        documents.append(
            DocumentItem(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                content=row["content"] if include_content else None,
            )
        )

    return DocumentListResponse(documents=documents)


@app.delete(
    "/documents/{document_id}",
    response_model=DeleteResponse,
    summary="Delete a document from a project",
)
async def delete_document(
    document_id: int,
    service: StorageService = Depends(get_database_service),
):
    await run_in_threadpool(service.delete_document, document_id)
    return DeleteResponse(status="success", message=f"Document {document_id} deleted")

@app.post("/generate",
          response_model=GenerateResponse,
          summary="Generate content based on a project ID")
async def generate_content(
    payload: ProjectRequest,
    studybuddy_service: StudyBuddyService = Depends(get_studybuddy_service),
    storage_service: StorageService = Depends(get_database_service),
):
    # Get all documents for the project
    document_ids = await run_in_threadpool(storage_service.list_documents, payload.project_id)
    
    if not document_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No documents found for project {payload.project_id}"
        )
    
    # Generate content for each document individually
    for doc_id in document_ids:
        doc = await run_in_threadpool(storage_service.get_document, doc_id)
        if not doc:
            continue
        
        doc_content = doc['content']
        
        # Generate flashcards for this document
        flashcards = await run_in_threadpool(studybuddy_service.generate_flashcards, doc_content)
        for flashcard in flashcards:
            await run_in_threadpool(
                storage_service.add_flashcard,
                doc_id,
                flashcard.question,
                flashcard.answer
            )
        
        # Generate exam questions for this document
        exam_questions = await run_in_threadpool(studybuddy_service.generate_practice_exam, doc_content)
        for question in exam_questions:
            # Ensure we have exactly 4 options
            if len(question.options) >= 4:
                await run_in_threadpool(
                    storage_service.add_exam_question,
                    doc_id,
                    question.question,
                    question.options[0],
                    question.options[1],
                    question.options[2],
                    question.options[3],
                    question.correctAnswer
                )
    
    # Generate summary with images from all documents combined
    all_content = []
    for doc_id in document_ids:
        doc = await run_in_threadpool(storage_service.get_document, doc_id)
        if doc:
            all_content.append(f"# {doc['title']}\n\n{doc['content']}")
    
    combined_content = "\n\n---\n\n".join(all_content)
    summary = await run_in_threadpool(studybuddy_service.generate_summary_with_images, combined_content)
    await run_in_threadpool(storage_service.update_project_summary, payload.project_id, summary)
    
    return GenerateResponse(status="success")


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
    project_overview = await run_in_threadpool(service.get_project_overview, payload.project_id)
    if project_overview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {payload.project_id} not found",
        )

    return SummaryResponse(summary=project_overview.summary or "")



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


@app.post("/add_document",
          response_model=AddDocumentResponse,
          summary="Add a document to a project")
async def add_document(
    payload: AddDocumentRequest,
    service: StorageService = Depends(get_database_service),
):
    document_id = await run_in_threadpool(
        service.create_document,
        payload.project_id,
        payload.title,
        payload.content
    )
    
    return AddDocumentResponse(
        document_id=document_id,
        message=f"Document '{payload.title}' successfully added to project {payload.project_id}"
    )


@app.post("/create_project",
          response_model=CreateProjectResponse,
          summary="Create a new project")
async def create_project(
    payload: CreateProjectRequest,
    service: StorageService = Depends(get_database_service),
):
    project_id = await run_in_threadpool(
        service.create_project,
        payload.user_id,
        payload.name,
        ""  # Empty summary
    )
    
    return CreateProjectResponse(
        project_id=project_id,
        message=f"Project '{payload.name}' successfully created"
    )


__all__ = ["app"]


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
