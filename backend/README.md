# StudyBuddy Backend

This folder contains a self-hosted FastAPI service that mirrors the behaviour of the original Google AI integration used by the StudyBuddy frontend.  The service wraps a locally hosted large language model (LLM) and an optional image generation pipeline so you can run the entire workflow on-premise without relying on Google APIs.

## Features

- **Flashcards** – `POST /flashcards` converts uploaded source material into question/answer pairs.
- **Practice exam** – `POST /practice-exam` returns multiple choice questions with the correct answer flagged.
- **Summary with images** – `POST /summary-with-images` produces a Markdown summary and inlines `data:` URLs for any generated images.
- **Chat continuation** – `POST /chat` appends a new assistant response to an existing conversation.
- **Health check** – `GET /health` confirms the service is up.

All endpoints accept and return exactly the same payloads that the frontend expects from `services/geminiService.ts`, so you can switch the UI over to this backend by replacing the Google client with `fetch` calls.

## Model choices (<= 16 GB VRAM)

The defaults target readily available open models that comfortably run on a single 16 GB GPU when loaded in half precision:

- **Text generation** – [`mistralai/Mistral-7B-Instruct-v0.2`](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.2)
- **Image generation** – [`stabilityai/stable-diffusion-2-1-base`](https://huggingface.co/stabilityai/stable-diffusion-2-1-base)

You can swap either model by setting the environment variables listed below.

> [!TIP]
> When running entirely on CPU the service still works, but responses will be significantly slower.  The code automatically switches to float32 and CPU execution when CUDA is unavailable.

## Quick start

1. **Install dependencies**

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **(Optional) Configure models**

   Create a `.env` file inside `backend/` to override defaults:

   ```bash
   echo "STUDYBUDDY_TEXT_MODEL_ID=mistralai/Mixtral-8x7B-Instruct-v0.1" >> .env
   echo "STUDYBUDDY_ENABLE_IMAGE_GENERATION=false" >> .env  # disable the image pipeline
   ```

3. **Run the API**

   ```bash
   uvicorn backend.main:app --reload
   ```

   The server listens on `http://127.0.0.1:8000` by default.

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `STUDYBUDDY_TEXT_MODEL_ID` | `mistralai/Mistral-7B-Instruct-v0.2` | Hugging Face model id for text generation. |
| `STUDYBUDDY_IMAGE_MODEL_ID` | `stabilityai/stable-diffusion-2-1-base` | Diffusers checkpoint for image generation. |
| `STUDYBUDDY_MAX_NEW_TOKENS` | `512` | Cap on generated tokens per request. |
| `STUDYBUDDY_TEMPERATURE` | `0.7` | Sampling temperature for the LLM. |
| `STUDYBUDDY_ENABLE_IMAGE_GENERATION` | `true` | Set to `false` to skip image creation entirely. |

## Frontend integration

Update `services/geminiService.ts` to replace the Google client with REST calls to the endpoints above.  The payload shapes can stay identical to the current implementation, so the rest of the React components continue working unchanged.

## Testing the endpoints

With the server running you can send a request using `curl` or any API client:

```bash
curl -X POST http://127.0.0.1:8000/flashcards \
  -H "Content-Type: application/json" \
  -d '{"scriptContent": "## Sample script\nThe mitochondria is the powerhouse of the cell."}'
```

Each endpoint returns either JSON or plain text (for `/chat`), and FastAPI automatically produces OpenAPI docs at `http://127.0.0.1:8000/docs`.

