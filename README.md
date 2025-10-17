# StudyBuddy AI 🎓✨



**StudyBuddy** is your personal AI-powered study companion that transforms your lecture notes and study materials into interactive learning tools! 📚 Whether you need flashcards for quick revision, practice exams to test your knowledge, or visual summaries with AI-generated diagrams, StudyBuddy has you covered. Built with a self-hosted backend running state-of-the-art open-source models (Llama, Mistral, Stable Diffusion), it keeps your data private while delivering powerful AI capabilities. Plus, you can chat with an AI tutor that understands your study materials! 🤖💡

## Use Cases

- **Summary** 📝: Generate comprehensive, well-structured Markdown summaries of your study materials, complete with AI-generated diagrams and illustrations. The AI identifies key concepts that benefit from visual aids and creates custom images on-the-fly to enhance understanding. Perfect for condensing dense textbooks or lecture notes into digestible visual guides!

- **Flashcards** 🃏: Automatically extract key concepts, definitions, and facts from your materials and transform them into question-answer flashcard pairs. Ideal for memorization and quick review sessions. The AI focuses on the most important information, so you don't waste time on trivial details.

- **Exam Questions** 📋: Generate realistic multiple-choice practice exams based on your study content. Each question comes with four options and a verified correct answer. Great for testing your knowledge before the real exam and identifying gaps in your understanding!

- **Chat** 💬: Have an interactive conversation with an AI tutor that has full context of your study materials. Ask questions, request clarifications, or explore topics in depth. The AI adapts its responses to your learning style and provides clear, actionable explanations.

## Quick Start

### 🚀 Backend Setup

The backend runs locally using PyTorch and Hugging Face models. You'll need a GPU with at least 8GB VRAM for optimal performance.

**Installation:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Running the Server:**

```bash
# From the project root
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Check `http://localhost:8000/health` to verify it's running!

### ⚙️ Configuration Options

You can customize the AI models via environment variables or a `.env` file in the `backend/` directory:

```bash
# Text generation model (for flashcards, exams, summaries, chat)
STUDYBUDDY_TEXT_MODEL_ID=meta-llama/Llama-3.1-8B-Instruct

# Image generation model (for summary diagrams)
STUDYBUDDY_IMAGE_MODEL_ID=stabilityai/sdxl-turbo

# Generation parameters
STUDYBUDDY_MAX_NEW_TOKENS=512
STUDYBUDDY_TEMPERATURE=0.7

# Disable image generation to save VRAM
STUDYBUDDY_ENABLE_IMAGE_GENERATION=true
```

**🎯 Model Recommendations:**

Different models have different strengths and hardware requirements. Here are some great options:

**Text Models** (choose based on your GPU):
- `Qwen/Qwen2.5-7B-Instruct` - Best for structured output & JSON (7B, ~8GB VRAM) ⭐
- `meta-llama/Llama-3.1-8B-Instruct` - Excellent all-rounder (8B, ~8GB VRAM)
- `mistralai/Mistral-Nemo-Instruct-2407` - Great quality (12B, ~12GB VRAM)

**Image Models** (for summary diagrams):
- `stabilityai/sdxl-turbo` - Fast & good quality (recommended!) ⭐
- `stabilityai/stable-diffusion-xl-base-1.0` - Best quality, slower
- `ByteDance/SDXL-Lightning` - Ultra-fast, great for real-time

💡 **Why choose different models?** Larger models are smarter but need more VRAM and run slower. Smaller models are faster and use less memory but may struggle with complex reasoning. Pick what fits your hardware and patience level!

### 🎨 Frontend Setup

The frontend is a React + TypeScript app built with Vite.

**Installation:**

```bash
cd frontend
npm install
```

**Running the Dev Server:**

```bash
npm run dev
```

The app will be available at `http://localhost:5173` (or the port shown in your terminal).

### 🌐 Connecting Frontend to Backend

By default, the frontend expects the backend at `http://localhost:8000`. If your backend runs on a different machine or port:

1. Edit `frontend/services/geminiService.ts`
2. Change the `API_BASE_URL` constant:
   ```typescript
   const API_BASE_URL = 'http://your-backend-ip:8000';
   ```

**⚠️ Security Disclaimer:**

This backend has **no authentication, rate limiting, or API keys**. It's designed for local, personal use. If you expose it to the internet:
- Anyone can access it and consume your GPU resources
- Anyone can send arbitrary content to your models
- Consider adding authentication (e.g., API keys, OAuth) before deployment
- Use a reverse proxy (nginx, Caddy) with rate limiting for production

For personal use on `localhost` or a trusted local network, you're fine! 😊

## Collaboration 🤝

Contributions are welcome and appreciated! 🎉 Whether you want to add features, fix bugs, improve documentation, or suggest better models, feel free to:

- 🐛 Open an issue for bugs or feature requests
- 🔧 Submit pull requests (please follow existing code style)
- 💡 Share your ideas in discussions
- ⭐ Star the repo if you find it useful!

This is a hobby project built for fun and learning, so don't be shy - all skill levels are welcome! Let's make studying suck less together. 📖✨

## Citation 📄

If you use StudyBuddy in academic work, research, or commercial projects, please provide attribution:

```
StudyBuddy AI - An open-source AI-powered study companion
GitHub: https://github.com/SvenPfiffner/StudyBuddy
Author: Sven Pfiffner
Year: 2025
```

For commercial use, please ensure compliance with the licenses of the underlying models:
- Llama 3.1: Meta's License Agreement
- Mistral Models: Apache 2.0
- Stable Diffusion: CreativeML Open RAIL-M License
- Qwen Models: Apache 2.0

This project itself is provided as-is for educational and personal use. 🎓

