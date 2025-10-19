"""Tests covering the FastAPI routes defined in :mod:`backend.main`."""

from __future__ import annotations

import sys
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


from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.main import app
from backend.service import get_service


class StubService:
    """Test double emulating :class:`backend.service.StudyBuddyService`."""

    def __init__(self) -> None:
        self.flashcards_response = [
            {"question": "What is AI?", "answer": "Artificial intelligence."},
            {"question": "What is ML?", "answer": "Machine learning."},
        ]
        self.exam_response = [
            {
                "question": "Pick the odd one out.",
                "options": ["CPU", "GPU", "Banana", "TPU"],
                "correctAnswer": "Banana",
            }
        ]
        self.summary_response = "A concise summary with illustrative images."
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

    def generate_flashcards(self, script: str):  # pragma: no cover - exercised via API
        self._remember("generate_flashcards", script)
        self._maybe_raise("generate_flashcards")
        return self.flashcards_response

    def generate_practice_exam(self, script: str):  # pragma: no cover - exercised via API
        self._remember("generate_practice_exam", script)
        self._maybe_raise("generate_practice_exam")
        return self.exam_response

    def generate_summary_with_images(self, script: str):  # pragma: no cover
        self._remember("generate_summary_with_images", script)
        self._maybe_raise("generate_summary_with_images")
        return self.summary_response

    def continue_chat(self, history, system_instruction, message):  # pragma: no cover
        self._remember("continue_chat", history, system_instruction, message)
        self._maybe_raise("continue_chat")
        return self.chat_response

    def generate_image(self, prompt: str):  # pragma: no cover - exercised via API
        self._remember("generate_image", prompt)
        self._maybe_raise("generate_image")
        return self.image_response


@pytest.fixture
def client():
    """Yield a :class:`TestClient` backed by the stubbed service."""

    stub = StubService()
    app.dependency_overrides[get_service] = lambda: stub

    with TestClient(app) as test_client:
        test_client.app.state.stub_service = stub
        yield test_client

    app.dependency_overrides.clear()
    if hasattr(app.state, "stub_service"):
        delattr(app.state, "stub_service")


def get_stub(client: TestClient) -> StubService:
    return client.app.state.stub_service  # type: ignore[return-value]


def test_healthcheck_reports_backend_settings(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload == {
        "status": "ok",
        "textModel": "meta-llama/Llama-3.1-8B-Instruct",
        "imageModel": "stabilityai/sdxl-turbo",
    }


def test_flashcards_returns_stubbed_response(client: TestClient) -> None:
    stub = get_stub(client)

    response = client.post("/flashcards", json={"scriptContent": "chapter 1"})

    assert response.status_code == 200
    assert response.json() == stub.flashcards_response
    assert stub.calls["generate_flashcards"] == ("chapter 1",)


def test_flashcards_requires_script_content(client: TestClient) -> None:
    response = client.post("/flashcards", json={})

    assert response.status_code == 422
    assert any(err["loc"][-1] == "scriptContent" for err in response.json()["detail"])


def test_practice_exam_returns_stubbed_response(client: TestClient) -> None:
    stub = get_stub(client)

    response = client.post("/practice-exam", json={"scriptContent": "chapter 2"})

    assert response.status_code == 200
    assert response.json() == stub.exam_response
    assert stub.calls["generate_practice_exam"] == ("chapter 2",)


def test_practice_exam_requires_script_content(client: TestClient) -> None:
    response = client.post("/practice-exam", json={})

    assert response.status_code == 422
    assert any(err["loc"][-1] == "scriptContent" for err in response.json()["detail"])


def test_summary_with_images_returns_envelope(client: TestClient) -> None:
    stub = get_stub(client)

    response = client.post("/summary-with-images", json={"scriptContent": "chapter 3"})

    assert response.status_code == 200
    assert response.json() == {"summary": stub.summary_response}
    assert stub.calls["generate_summary_with_images"] == ("chapter 3",)


def test_summary_with_images_requires_script_content(client: TestClient) -> None:
    response = client.post("/summary-with-images", json={})

    assert response.status_code == 422
    assert any(err["loc"][-1] == "scriptContent" for err in response.json()["detail"])


def test_chat_returns_stubbed_message(client: TestClient) -> None:
    stub = get_stub(client)
    payload = {
        "history": [
            {"role": "user", "parts": [{"text": "Hi"}]},
            {"role": "model", "parts": [{"text": "Hello"}]},
        ],
        "systemInstruction": "Be brief",
        "message": "Summarise the lesson",
    }

    response = client.post("/chat", json=payload)

    assert response.status_code == 200
    assert response.json() == {"message": stub.chat_response}
    history, system_instruction, message = stub.calls["continue_chat"]
    assert system_instruction == payload["systemInstruction"]
    assert message == payload["message"]
    assert [item.model_dump() for item in history] == payload["history"]


def test_chat_requires_full_payload(client: TestClient) -> None:
    response = client.post("/chat", json={})

    assert response.status_code == 422
    missing_fields = {err["loc"][-1] for err in response.json()["detail"]}
    assert {"history", "systemInstruction", "message"} <= missing_fields


def test_generate_image_returns_stubbed_payload(client: TestClient) -> None:
    stub = get_stub(client)

    response = client.post("/generate-image", json={"prompt": "Draw a cat"})

    assert response.status_code == 200
    assert response.json() == {"image": stub.image_response}
    assert stub.calls["generate_image"] == ("Draw a cat",)


def test_generate_image_requires_prompt(client: TestClient) -> None:
    response = client.post("/generate-image", json={})

    assert response.status_code == 422
    assert any(err["loc"][-1] == "prompt" for err in response.json()["detail"])


def test_chat_http_exception_surfaces_unchanged(client: TestClient) -> None:
    stub = get_stub(client)
    stub.exceptions["continue_chat"] = HTTPException(status_code=418, detail="Nope")

    payload = {
        "history": [],
        "systemInstruction": "irrelevant",
        "message": "trigger failure",
    }

    response = client.post("/chat", json=payload)

    assert response.status_code == 418
    assert response.json() == {"detail": "Nope"}
