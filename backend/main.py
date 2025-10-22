"""FastAPI entry point exposing the StudyBuddy REST API."""

from __future__ import annotations

import os
os.environ.setdefault("VLLM_WORKER_MULTIPROC_METHOD", "spawn")

import logging
import re
from textwrap import dedent
from typing import Any, List, Sequence

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .config import get_settings
from .schemas import (
    AddDocumentRequest,
    AddDocumentResponse,
    ChatHistoryResponse,
    ChatMessage,
    ChatPart,
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


def _normalise_option_text(text: str) -> str:
    cleaned = re.sub(r"^[a-d][).:\-\s]+", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned.rstrip('.')


def _resolve_answer_letter(correct_answer: str, options: Sequence[str]) -> str:
    letters = ("A", "B", "C", "D")
    if len(options) < len(letters):
        raise ValueError("expected four answer options")

    answer = correct_answer.strip()
    if not answer:
        raise ValueError("empty correct answer")

    upper_answer = answer.upper()
    if upper_answer in letters:
        return upper_answer

    letter_match = re.match(r"^([A-D])\b", upper_answer)
    if letter_match:
        return letter_match.group(1)

    normalised_answer = _normalise_option_text(answer)
    for idx, option in enumerate(options[:4]):
        if _normalise_option_text(option) == normalised_answer:
            return letters[idx]

    for idx, option in enumerate(options[:4]):
        if normalised_answer and normalised_answer in _normalise_option_text(option):
            return letters[idx]

    raise ValueError(f"could not map answer '{correct_answer}' to one of the options")


MAX_CHAT_HISTORY_MESSAGES = 20
MAX_CHAT_HISTORY_CHARS = 5000
MAX_DOCUMENT_CONTEXT_CHARS = 12000
_TRUNCATION_SUFFIX = "\n[... truncated for length ...]"
_HISTORY_PREFIX = "[...] "


_ROLE_DB_TO_API = {"user": "user", "assistant": "model", "system": "model"}


def _truncate_text(text: str, limit: int) -> tuple[str, bool]:
    if limit <= 0:
        return "", True
    if len(text) <= limit:
        return text, False
    suffix = _TRUNCATION_SUFFIX
    if limit <= len(suffix):
        return suffix.strip(), True
    return text[: limit - len(suffix)] + suffix, True


def _row_to_chat_message(row: Any) -> ChatMessage:
    role = _ROLE_DB_TO_API.get(row["role"], "model")
    return ChatMessage(role=role, parts=[ChatPart(text=row["content"])])


def _compress_chat_history(history: Sequence[ChatMessage]) -> List[ChatMessage]:
    if not history:
        return []

    limited_history = list(history)[-MAX_CHAT_HISTORY_MESSAGES:]
    selected: List[ChatMessage] = []
    used_chars = 0

    for message in reversed(limited_history):  # prioritise the most recent entries
        message_text = " ".join(part.text for part in message.parts).strip()
        if not message_text:
            selected.append(message)
            continue

        available = MAX_CHAT_HISTORY_CHARS - used_chars
        if available <= 0:
            break

        if len(message_text) > available:
            truncated_text, _ = _truncate_text(message_text[-available:], available)
            truncated_text = (_HISTORY_PREFIX + truncated_text) if len(truncated_text) < len(message_text) else truncated_text
            selected.append(ChatMessage(role=message.role, parts=[ChatPart(text=truncated_text)]))
            used_chars = MAX_CHAT_HISTORY_CHARS
            break

        selected.append(message)
        used_chars += len(message_text)

    selected.reverse()
    if len(selected) < len(history):
        logger.debug("Chat history truncated to %s messages and %s chars", len(selected), used_chars)
    return selected


def _build_system_instruction(project_name: str, documents: Sequence[Any]) -> str:
    print("Building system instruction with documents:", documents)
    rendered_sections: List[str] = []
    remaining = MAX_DOCUMENT_CONTEXT_CHARS
    for doc in documents:
        content = doc["content"]
        print("Document content:", content)
        if not content:
            continue
        header = ""
        footer = ""
        overhead = len(header) + len(footer)
        if remaining <= overhead:
            break

        available_for_content = remaining - overhead
        snippet, truncated = _truncate_text(content.strip(), available_for_content)
        section = header + snippet + footer
        rendered_sections.append(section)
        remaining -= len(section) + 2  # account for the separator newlines
        if truncated and remaining <= 0:
            break

    rendered_documents = "\n\n".join(rendered_sections).strip()
    if not rendered_documents:
        rendered_documents = "[No document content available]"

    return dedent(
        f"""
        {rendered_documents}
        """
    ).strip()

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

    await run_in_threadpool(storage_service.clear_flashcards_for_project, payload.project_id)
    await run_in_threadpool(storage_service.clear_exam_questions_for_project, payload.project_id)
    
    # Generate content for each document individually
    for doc_id in document_ids:
        doc = await run_in_threadpool(storage_service.get_document, doc_id)
        if not doc:
            continue
        
        doc_content = f"Document Title: {doc['title']}\n\n{doc['content']}"
        
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
            if len(question.options) < 4:
                logger.warning(
                    "Skipping exam question with insufficient options for document %s", doc_id
                )
                continue

            try:
                answer_letter = _resolve_answer_letter(question.correctAnswer, question.options)
            except ValueError as exc:
                logger.warning("Skipping exam question for document %s: %s", doc_id, exc)
                continue

            await run_in_threadpool(
                storage_service.add_exam_question,
                doc_id,
                question.question,
                question.options[0],
                question.options[1],
                question.options[2],
                question.options[3],
                answer_letter,
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



@app.get(
    "/projects/{project_id}/chat",
    response_model=ChatHistoryResponse,
    summary="Retrieve the saved chat history for a project",
)
async def chat_history(
    project_id: int,
    service: StorageService = Depends(get_database_service),
):
    rows = await run_in_threadpool(service.list_chat_messages, project_id)
    messages = [_row_to_chat_message(row) for row in rows]
    return ChatHistoryResponse(messages=messages)


@app.post(
    "/projects/{project_id}/chat",
    response_model=ChatResponse,
    summary="Append a chat message and generate the assistant reply",
)
async def chat(
    project_id: int,
    payload: ChatRequest,
    studybuddy_service: StudyBuddyService = Depends(get_studybuddy_service),
    storage_service: StorageService = Depends(get_database_service),
):
    message = payload.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message must not be empty",
        )

    project_overview = await run_in_threadpool(storage_service.get_project_overview, project_id)
    if project_overview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Get all documents for the project
    documents = await run_in_threadpool(storage_service.list_documents_with_content, project_id)

    context = "\n\n".join(doc['content'] for doc in documents)

        
    history_rows = await run_in_threadpool(storage_service.list_chat_messages, project_id)
    history_messages = _compress_chat_history([_row_to_chat_message(row) for row in history_rows])

    try:
        reply = await run_in_threadpool(
            studybuddy_service.continue_chat_conversational,
            history_messages,
            context,
            message,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Chat generation failed for project %s", project_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Chat generation failed. Please try again.",
        ) from exc

    await run_in_threadpool(storage_service.add_chat_message, project_id, "user", message)
    await run_in_threadpool(storage_service.add_chat_message, project_id, "assistant", reply)

    updated_rows = await run_in_threadpool(storage_service.list_chat_messages, project_id)
    messages = [_row_to_chat_message(row) for row in updated_rows]
    return ChatResponse(messages=messages)


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
