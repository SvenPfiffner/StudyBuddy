"""Tests covering the FastAPI routes defined in :mod:`backend.main`."""

from __future__ import annotations

import sys
import sqlite3
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


class _CudaNamespace:
    def is_available(self) -> bool:  # pragma: no cover - simple stub
        return False

    def empty_cache(self) -> None:  # pragma: no cover - simple stub
        return None

    def synchronize(self) -> None:  # pragma: no cover - simple stub
        return None

    def device(self, index: int):  # pragma: no cover - simple stub
        class _DeviceContext:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        return _DeviceContext()


torch_stub = ModuleType("torch")
torch_stub.float16 = object()
torch_stub.float32 = object()
torch_stub.cuda = _CudaNamespace()


def _diffusers_pipeline_call(*args, **kwargs):  # pragma: no cover - exercised indirectly
    class _Image:
        def save(self, buffer, format="JPEG", quality=90):
            buffer.write(b"stub-image-bytes")

    return SimpleNamespace(images=[_Image()])


class _DummyDiffusionPipeline:
    def __init__(self) -> None:
        self.scheduler = SimpleNamespace(config={})

    def to(self, device: str) -> "_DummyDiffusionPipeline":
        return self

    def enable_attention_slicing(self) -> None:
        return None

    def __call__(self, *args, **kwargs):
        return _diffusers_pipeline_call(*args, **kwargs)


class _AutoPipelineForText2Image:
    @classmethod
    def from_pretrained(cls, *args, **kwargs) -> _DummyDiffusionPipeline:
        return _DummyDiffusionPipeline()


class _AutoencoderKL:
    @classmethod
    def from_pretrained(cls, *args, **kwargs) -> "_AutoencoderKL":
        return cls()


class _EulerDiscreteScheduler:
    @classmethod
    def from_config(cls, config):
        return SimpleNamespace()


diffusers_stub = ModuleType("diffusers")
diffusers_stub.AutoPipelineForText2Image = _AutoPipelineForText2Image
diffusers_stub.AutoencoderKL = _AutoencoderKL
diffusers_stub.EulerDiscreteScheduler = _EulerDiscreteScheduler


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
        return [SimpleNamespace(outputs=[SimpleNamespace(text="stub-text")])]


vllm_stub = ModuleType("vllm")
vllm_stub.LLM = _FakeLLM
vllm_stub.SamplingParams = _SamplingParams

vllm_sampling_stub = ModuleType("vllm.sampling_params")
vllm_sampling_stub.GuidedDecodingParams = _GuidedDecodingParams


class _Tokenizer:
    def __init__(self) -> None:
        self.pad_token_id = None
        self.eos_token_id = 0


class _AutoTokenizer:
    @classmethod
    def from_pretrained(cls, *args, **kwargs) -> _Tokenizer:
        return _Tokenizer()


class _AutoModelForCausalLM:
    @classmethod
    def from_pretrained(cls, *args, **kwargs) -> "_AutoModelForCausalLM":
        return cls()


class _BitsAndBytesConfig:
    def __init__(self, **kwargs) -> None:
        pass


def _pipeline(task, model, tokenizer, return_full_text=False, **kwargs):
    class _Pipeline:
        def __init__(self, tokenizer: _Tokenizer) -> None:
            self.tokenizer = tokenizer

        def __call__(self, prompt, **kwargs):
            return [{"generated_text": "stub"}]

    return _Pipeline(tokenizer)


transformers_stub = ModuleType("transformers")
transformers_stub.AutoTokenizer = _AutoTokenizer
transformers_stub.AutoModelForCausalLM = _AutoModelForCausalLM
transformers_stub.BitsAndBytesConfig = _BitsAndBytesConfig
transformers_stub.pipeline = _pipeline


sys.modules["torch"] = torch_stub
sys.modules["diffusers"] = diffusers_stub
sys.modules["transformers"] = transformers_stub
sys.modules["vllm"] = vllm_stub
sys.modules["vllm.sampling_params"] = vllm_sampling_stub


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.main import app
from backend.service import get_studybuddy_service
from backend.storageservice.storageservice import StorageService, get_database_service


def _create_threadsafe_storage_service(db_path: str) -> StorageService:
    return StorageService(db_path)


class StubService:
    """Test double emulating :class:`backend.service.StudyBuddyService`."""

    def __init__(self) -> None:
        self.chat_response = "Hello from StudyBuddy!"
        self.image_response = "YmFzZTY0LWltYWdlLWRhdGE="
        self.calls: dict[str, tuple] = {}
        self.exceptions: dict[str, HTTPException] = {}

    def _remember(self, method: str, *args) -> None:
        self.calls[method] = args

    def _maybe_raise(self, method: str) -> None:
        exc = self.exceptions.get(method)
        if exc is not None:
            raise exc

    def continue_chat(self, history, system_instruction, message):  # pragma: no cover
        self._remember("continue_chat", history, system_instruction, message)
        self._maybe_raise("continue_chat")
        return self.chat_response

    def generate_image(self, prompt: str):  # pragma: no cover - exercised via API
        self._remember("generate_image", prompt)
        self._maybe_raise("generate_image")
        return self.image_response


@pytest.fixture
def storage_service(tmp_path):
    service = _create_threadsafe_storage_service(str(tmp_path / "studybuddy.db"))
    try:
        yield service
    finally:
        service.close()


@pytest.fixture
def client(storage_service):
    """Yield a :class:`TestClient` backed by stubbed dependencies."""

    stub = StubService()
    app.dependency_overrides[get_studybuddy_service] = lambda: stub
    app.dependency_overrides[get_database_service] = lambda: storage_service

    with TestClient(app) as test_client:
        test_client.app.state.stub_service = stub
        test_client.app.state.storage_service = storage_service
        yield test_client

    app.dependency_overrides.clear()
    for attr in ("stub_service", "storage_service"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)


def get_stub(client: TestClient) -> StubService:
    return client.app.state.stub_service  # type: ignore[return-value]


def get_storage(client: TestClient) -> StorageService:
    return client.app.state.storage_service  # type: ignore[return-value]


def test_healthcheck_reports_backend_settings(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["textModel"] == "meta-llama/Llama-3.1-8B-Instruct"
    # Image generation is disabled by default in settings, so the model id is omitted.
    assert payload["imageModel"] is None


def _seed_project_with_content(service: StorageService, *, summary: str = "Cells 101") -> dict[str, int]:
    user_id = service.create_user("alice")
    project_id = service.create_project(user_id, "Biology", summary=summary)
    doc_intro = service.create_document(project_id, "Introduction", "Cells are the building blocks of life")
    doc_mitosis = service.create_document(project_id, "Mitosis", "Cells divide to reproduce")

    service.add_flashcard(doc_intro, "What is a cell?", "The basic structural unit of life.")
    service.add_flashcard(doc_mitosis, "Name the stages of mitosis.", "Prophase, metaphase, anaphase, telophase.")

    service.add_exam_question(
        doc_intro,
        question="Which organelle generates energy for the cell?",
        option_a="Mitochondria",
        option_b="Nucleus",
        option_c="Ribosome",
        option_d="Golgi apparatus",
        answer_letter="A",
    )
    service.add_exam_question(
        doc_mitosis,
        question="During which phase do chromosomes align at the center?",
        option_a="Anaphase",
        option_b="Metaphase",
        option_c="Telophase",
        option_d="Prophase",
        answer_letter="B",
    )

    return {"user_id": user_id, "project_id": project_id, "docs": (doc_intro, doc_mitosis)}


def test_flashcards_endpoint_returns_project_cards(client: TestClient) -> None:
    service = get_storage(client)
    project_info = _seed_project_with_content(service)

    response = client.post("/flashcards", json={"project_id": project_info["project_id"]})

    assert response.status_code == 200
    assert response.json() == [
        {"question": "What is a cell?", "answer": "The basic structural unit of life."},
        {
            "question": "Name the stages of mitosis.",
            "answer": "Prophase, metaphase, anaphase, telophase.",
        },
    ]


def test_flashcards_endpoint_returns_empty_list_for_project_without_cards(client: TestClient) -> None:
    service = get_storage(client)
    user_id = service.create_user("bob")
    project_id = service.create_project(user_id, "Chemistry", summary="Atoms and molecules")
    service.create_document(project_id, "Overview", "Content")

    response = client.post("/flashcards", json={"project_id": project_id})

    assert response.status_code == 200
    assert response.json() == []


def test_flashcards_endpoint_requires_project_id(client: TestClient) -> None:
    response = client.post("/flashcards", json={})

    assert response.status_code == 422
    assert any(err["loc"][-1] == "project_id" for err in response.json()["detail"])


def test_practice_exam_endpoint_returns_combined_questions(client: TestClient) -> None:
    service = get_storage(client)
    project_info = _seed_project_with_content(service)

    response = client.post("/practice-exam", json={"project_id": project_info["project_id"]})

    assert response.status_code == 200
    assert response.json() == [
        {
            "question": "Which organelle generates energy for the cell?",
            "options": [
                "Mitochondria",
                "Nucleus",
                "Ribosome",
                "Golgi apparatus",
            ],
            "correctAnswer": "A",
        },
        {
            "question": "During which phase do chromosomes align at the center?",
            "options": [
                "Anaphase",
                "Metaphase",
                "Telophase",
                "Prophase",
            ],
            "correctAnswer": "B",
        },
    ]


def test_practice_exam_endpoint_handles_project_with_no_documents(client: TestClient) -> None:
    service = get_storage(client)
    user_id = service.create_user("chris")
    project_id = service.create_project(user_id, "Physics", summary="Motion and forces")

    response = client.post("/practice-exam", json={"project_id": project_id})

    assert response.status_code == 200
    assert response.json() == []


def test_practice_exam_endpoint_requires_project_id(client: TestClient) -> None:
    response = client.post("/practice-exam", json={})

    assert response.status_code == 422
    assert any(err["loc"][-1] == "project_id" for err in response.json()["detail"])


def test_summary_with_images_returns_project_summary(client: TestClient) -> None:
    service = get_storage(client)
    project_info = _seed_project_with_content(service, summary="Cells overview")

    response = client.post("/summary-with-images", json={"project_id": project_info["project_id"]})

    assert response.status_code == 200
    assert response.json() == {"summary": "Cells overview"}


def test_summary_with_images_returns_empty_summary_when_none_stored(client: TestClient) -> None:
    service = get_storage(client)
    user_id = service.create_user("drew")
    project_id = service.create_project(user_id, "History", summary=None)

    response = client.post("/summary-with-images", json={"project_id": project_id})

    assert response.status_code == 200
    assert response.json() == {"summary": ""}


def test_summary_with_images_requires_project_id(client: TestClient) -> None:
    response = client.post("/summary-with-images", json={})

    assert response.status_code == 422
    assert any(err["loc"][-1] == "project_id" for err in response.json()["detail"])


def test_chat_history_endpoint_returns_stored_messages(client: TestClient) -> None:
    service = get_storage(client)
    project_info = _seed_project_with_content(service)
    service.add_chat_message(project_info["project_id"], "user", "Hello")
    service.add_chat_message(project_info["project_id"], "assistant", "Hi there!")

    response = client.get(f"/projects/{project_info['project_id']}/chat")

    assert response.status_code == 200
    assert response.json() == {
        "messages": [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"text": "Hi there!"}]},
        ]
    }


def test_chat_append_generates_and_persists_reply(client: TestClient) -> None:
    stub = get_stub(client)
    service = get_storage(client)
    project_info = _seed_project_with_content(service)
    project_id = project_info["project_id"]
    service.add_chat_message(project_id, "user", "Previous question")
    service.add_chat_message(project_id, "assistant", "Previous answer")

    payload = {"message": "What is the next step?"}
    response = client.post(f"/projects/{project_id}/chat", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["messages"][-2]["parts"][0]["text"] == payload["message"]
    assert body["messages"][-1]["parts"][0]["text"] == stub.chat_response

    history, system_instruction, message = stub.calls["continue_chat"]
    assert message == payload["message"]
    assert len(history) == 2
    assert history[0].parts[0].text == "Previous question"
    assert history[1].parts[0].text == "Previous answer"
    assert "Introduction" in system_instruction

    stored_rows = service.list_chat_messages(project_id)
    assert [row["role"] for row in stored_rows][-2:] == ["user", "assistant"]


def test_chat_append_requires_non_empty_message(client: TestClient) -> None:
    service = get_storage(client)
    project_info = _seed_project_with_content(service)

    response = client.post(
        f"/projects/{project_info['project_id']}/chat",
        json={"message": "   "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Message must not be empty"


def test_chat_append_propagates_http_errors(client: TestClient) -> None:
    stub = get_stub(client)
    stub.exceptions["continue_chat"] = HTTPException(status_code=418, detail="Nope")
    service = get_storage(client)
    project_info = _seed_project_with_content(service)

    response = client.post(
        f"/projects/{project_info['project_id']}/chat",
        json={"message": "trigger failure"},
    )

    assert response.status_code == 418
    assert response.json() == {"detail": "Nope"}
