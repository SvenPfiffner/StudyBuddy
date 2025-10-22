"""Comprehensive tests for :mod:`backend.storageservice.storageservice`."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

class _SamplingParams:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class _GuidedDecodingParams:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class _FakeLLM:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def generate(self, prompts, params):  # pragma: no cover - exercised indirectly
        from types import SimpleNamespace

        return [SimpleNamespace(outputs=[SimpleNamespace(text="stub-text")])]


import types

vllm_stub = types.ModuleType("vllm")
vllm_stub.LLM = _FakeLLM
vllm_stub.SamplingParams = _SamplingParams

vllm_sampling_stub = types.ModuleType("vllm.sampling_params")
vllm_sampling_stub.GuidedDecodingParams = _GuidedDecodingParams

sys.modules.setdefault("vllm", vllm_stub)
sys.modules.setdefault("vllm.sampling_params", vllm_sampling_stub)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.schemas import ExamQuestion, Flashcard, Project
from backend.storageservice.storageservice import StorageService


@pytest.fixture
def storage_service(tmp_path) -> StorageService:
    service = StorageService(str(tmp_path / "storage.db"))
    try:
        yield service
    finally:
        service.close()


def _create_user_and_project(service: StorageService, *, name: str = "alice", summary: str | None = "Overview") -> tuple[int, int]:
    user_id = service.create_user(name)
    project_id = service.create_project(user_id, f"{name}'s project", summary=summary)
    return user_id, project_id


def test_create_and_retrieve_users(storage_service: StorageService) -> None:
    user_id = storage_service.create_user("alice")
    retrieved = storage_service.get_user_by_name("alice")

    assert retrieved is not None
    assert retrieved["id"] == user_id
    assert retrieved["name"] == "alice"

    listing = storage_service.list_users()
    assert [row["name"] for row in listing] == ["alice"]


def test_create_user_enforces_unique_names(storage_service: StorageService) -> None:
    storage_service.create_user("unique")

    with pytest.raises(sqlite3.IntegrityError):
        storage_service.create_user("unique")


def test_create_project_initialises_chat_and_lists_projects(storage_service: StorageService) -> None:
    user_id = storage_service.create_user("bob")
    project_id = storage_service.create_project(user_id, "Biology", summary="Cells")
    storage_service.create_project(user_id, "Art", summary="Colors")

    projects = storage_service.list_projects(user_id)
    assert [row["name"] for row in projects] == ["Art", "Biology"]  # alphabetical ordering

    chat_id = storage_service.get_or_create_chat(project_id)
    assert isinstance(chat_id, int)

    # Calling again should reuse the same chat row
    assert storage_service.get_or_create_chat(project_id) == chat_id


def test_update_project_summary_and_fetch_overview(storage_service: StorageService) -> None:
    user_id, project_id = _create_user_and_project(storage_service, summary=None)

    overview_before = storage_service.get_project_overview(project_id)
    assert isinstance(overview_before, Project)
    assert overview_before.summary == ""

    storage_service.update_project_summary(project_id, "Updated summary")
    overview_after = storage_service.get_project_overview(project_id)
    assert overview_after is not None
    assert overview_after.summary == "Updated summary"


def test_get_project_overview_returns_none_when_missing(storage_service: StorageService) -> None:
    assert storage_service.get_project_overview(9999) is None


def test_delete_project_cascades_to_related_records(storage_service: StorageService) -> None:
    user_id, project_id = _create_user_and_project(storage_service)
    doc_id = storage_service.create_document(project_id, "Notes", "Important content")
    chunk_id = storage_service.add_chunk(doc_id, 0, "Chunk text")
    storage_service.set_chunk_embedding(chunk_id, b"\x00\x01", 2, "model")
    card_id = storage_service.add_flashcard(doc_id, "Q", "A")
    question_id = storage_service.add_exam_question(
        doc_id,
        "What?",
        "A",
        "B",
        "C",
        "D",
        "A",
    )
    storage_service.add_chat_message(project_id, "user", "Hello")

    storage_service.delete_project(project_id)

    assert storage_service.list_documents(project_id) == []
    assert storage_service.project_overview(user_id) == []

    cursor = storage_service.connection.execute("SELECT COUNT(*) FROM chats WHERE project_id = ?", (project_id,))
    assert cursor.fetchone()[0] == 0
    cursor = storage_service.connection.execute("SELECT COUNT(*) FROM flashcards WHERE id = ?", (card_id,))
    assert cursor.fetchone()[0] == 0
    cursor = storage_service.connection.execute("SELECT COUNT(*) FROM exam_questions WHERE id = ?", (question_id,))
    assert cursor.fetchone()[0] == 0
    cursor = storage_service.connection.execute("SELECT COUNT(*) FROM doc_chunks WHERE document_id = ?", (doc_id,))
    assert cursor.fetchone()[0] == 0


def test_document_update_variants(storage_service: StorageService) -> None:
    _, project_id = _create_user_and_project(storage_service, name="carol")
    doc_id = storage_service.create_document(project_id, "Draft", "Initial text")

    storage_service.update_document(doc_id, title="Draft v2", content="Revised text")
    row = storage_service.get_document(doc_id)
    assert row["title"] == "Draft v2"
    assert row["content"] == "Revised text"

    storage_service.update_document(doc_id, title="Final")
    row = storage_service.get_document(doc_id)
    assert row["title"] == "Final"

    storage_service.update_document(doc_id, content="Final text")
    row = storage_service.get_document(doc_id)
    assert row["content"] == "Final text"

    # No-op update should leave content unchanged
    storage_service.update_document(doc_id)
    row = storage_service.get_document(doc_id)
    assert row["content"] == "Final text"


def test_list_documents_handles_empty_and_returns_creation_order(storage_service: StorageService) -> None:
    _, project_id = _create_user_and_project(storage_service, name="dave")
    assert storage_service.list_documents(project_id) == []

    doc1 = storage_service.create_document(project_id, "One", "Text1")
    doc2 = storage_service.create_document(project_id, "Two", "Text2")

    assert storage_service.list_documents(project_id) == [doc1, doc2]


def test_chunk_operations(storage_service: StorageService) -> None:
    _, project_id = _create_user_and_project(storage_service, name="erin")
    doc_id = storage_service.create_document(project_id, "Chapter", "Content")

    chunk1 = storage_service.add_chunk(doc_id, 0, "Intro")
    chunk2 = storage_service.add_chunk(doc_id, 1, "Body")
    storage_service.bulk_add_chunks(doc_id, [(2, "Conclusion")])

    storage_service.set_chunk_embedding(chunk1, b"\x00\x01", 2, "test-model")

    chunks = storage_service.list_chunks(doc_id)
    assert [c["seq"] for c in chunks] == [0, 1, 2]

    embeddings = storage_service.fetch_project_chunk_embeddings(project_id)
    assert embeddings == [(chunk1, b"\x00\x01", 2, "test-model")]

    fetched = storage_service.get_chunks_by_ids([chunk2, chunk1])
    fetched_ids = [row["id"] for row in fetched]
    assert set(fetched_ids) == {chunk1, chunk2}
    assert len(fetched_ids) == 2

    assert storage_service.get_chunks_by_ids([]) == []


def test_flashcard_crud(storage_service: StorageService) -> None:
    _, project_id = _create_user_and_project(storage_service, name="frank")
    doc_id = storage_service.create_document(project_id, "Doc", "Content")

    card1 = storage_service.add_flashcard(doc_id, "Front1", "Back1")
    card2 = storage_service.add_flashcard(doc_id, "Front2", "Back2")

    flashcards = storage_service.list_flashcards(doc_id)
    assert flashcards == [
        Flashcard(question="Front1", answer="Back1"),
        Flashcard(question="Front2", answer="Back2"),
    ]

    storage_service.delete_flashcard(card1)
    remaining = storage_service.list_flashcards(doc_id)
    assert remaining == [Flashcard(question="Front2", answer="Back2")]

    storage_service.delete_flashcard(card2)
    assert storage_service.list_flashcards(doc_id) == []


def test_exam_question_crud_and_validation(storage_service: StorageService) -> None:
    _, project_id = _create_user_and_project(storage_service, name="gina")
    doc_id = storage_service.create_document(project_id, "Doc", "Content")

    question_id = storage_service.add_exam_question(
        doc_id,
        question="Pick one",
        option_a="A",
        option_b="B",
        option_c="C",
        option_d="D",
        answer_letter="D",
    )

    questions = storage_service.list_exam_questions(doc_id)
    assert questions == [
        ExamQuestion(
            question="Pick one",
            options=["A", "B", "C", "D"],
            correctAnswer="D",
        )
    ]

    storage_service.delete_exam_question(question_id)
    assert storage_service.list_exam_questions(doc_id) == []

    with pytest.raises(sqlite3.IntegrityError):
        storage_service.add_exam_question(
            doc_id,
            question="Invalid",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            answer_letter="Z",
        )


def test_chat_flow_and_limits(storage_service: StorageService) -> None:
    _, project_id = _create_user_and_project(storage_service, name="henry")

    chat_id = storage_service.get_or_create_chat(project_id)
    storage_service.add_chat_message(project_id, "user", "Hi")
    storage_service.add_chat_message(project_id, "assistant", "Hello")
    storage_service.add_chat_message(project_id, "user", "Thanks")

    full_history = storage_service.list_chat_messages(project_id)
    assert [msg["content"] for msg in full_history] == ["Hi", "Hello", "Thanks"]

    limited_history = storage_service.list_chat_messages(project_id, limit=2)
    assert [msg["content"] for msg in limited_history] == ["Hello", "Thanks"]

    # Ensure chat id is reused and stable
    assert storage_service.get_or_create_chat(project_id) == chat_id


def test_list_chat_messages_returns_empty_for_projects_without_history(storage_service: StorageService) -> None:
    _, project_id = _create_user_and_project(storage_service, name="isaac")

    assert storage_service.list_chat_messages(project_id) == []
    assert storage_service.list_chat_messages(42, limit=5) == []


def test_project_overview_view_counts_related_records(storage_service: StorageService) -> None:
    user_id, project_id = _create_user_and_project(storage_service, name="iris")
    doc1 = storage_service.create_document(project_id, "One", "abc")
    doc2 = storage_service.create_document(project_id, "Two", "abcd")

    storage_service.add_flashcard(doc1, "F1", "B1")
    storage_service.add_flashcard(doc2, "F2", "B2")
    storage_service.add_exam_question(
        doc1,
        "Q1",
        "A",
        "B",
        "C",
        "D",
        "A",
    )
    storage_service.add_exam_question(
        doc2,
        "Q2",
        "A",
        "B",
        "C",
        "D",
        "B",
    )

    overview_rows = storage_service.project_overview(user_id)
    assert len(overview_rows) == 1
    row = overview_rows[0]
    assert row["project_id"] == project_id
    assert row["document_count"] == 2
    assert row["flashcard_count"] == 2
    assert row["exam_question_count"] == 2


def test_document_stats_view_reports_chunk_metrics(storage_service: StorageService) -> None:
    _, project_id = _create_user_and_project(storage_service, name="jane")
    doc_id = storage_service.create_document(project_id, "Doc", "abcd")

    storage_service.add_chunk(doc_id, 0, "A")
    chunk_with_embedding = storage_service.add_chunk(doc_id, 1, "B")
    storage_service.set_chunk_embedding(chunk_with_embedding, b"\x00", 1, "model")

    stats = storage_service.document_stats(project_id)
    assert len(stats) == 1
    row = stats[0]
    assert row["document_id"] == doc_id
    assert row["content_len_chars"] == 4
    assert row["chunk_count"] == 2
    assert row["chunk_with_emb_count"] == 1
