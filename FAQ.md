# FAQ

This markdown contains some commonly asked questions about the program and installation process. If you are stuck, please consult below before you raise an issue.

<details>
<summary><strong>How do I install and run StudyBuddy (backend & frontend)?</strong></summary>

Follow these steps for a local installation:

- Backend (Python):

```bash
# create and activate a virtualenv
python -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r backend/requirements.txt

# run the API server (example)
python backend/main.py
```

- Frontend (TypeScript / Vite):

```bash
cd frontend
npm install
npm run dev
```

</details>

<details>
<summary><strong>The backend won't start — I see an error like "module not found" or ImportError.</strong></summary>

Common causes and fixes:

- You're in the wrong Python environment. Make sure the virtual environment is activated and `pip install -r backend/requirements.txt` completed without errors.
- The working directory matters when running locally. Run the backend from the repository root or `backend/` depending on the project's entry point (try `python -m backend.main` if simple runs fail).
- If a package is missing, run `pip install <package>` or re-run the requirements install. Check for typos in `requirements.txt`.
- Check Python version compatibility. The project targets Python 3.11. Use 3.10+ if you encounter problems.

If the error persists, capture the full traceback and consult the `backend/` log output (or the terminal) and include the traceback when opening an issue.

</details>

<details>
<summary><strong>The frontend fails to load or shows a blank page.</strong></summary>

Checklist to debug:

- Open the browser devtools (Console + Network). Look for JS errors or failing network requests to the backend (CORS errors, 404s, 500s).
- Ensure the frontend dev server is running (`npm run dev`) and that the app URL matches the dev server printed in the terminal (usually `http://localhost:5173` for Vite).
- Confirm the backend API is running on the expected port and the frontend's environment config (if any) points to the correct backend URL.
- If you changed TypeScript or React code, restart the dev server to flush cached builds.

Share the browser console output when asking for help — it speeds up diagnosis.

</details>

<details>
<summary><strong>Requests to the backend fail with CORS blocked or network errors.</strong></summary>

This usually means the backend isn't allowing the frontend origin.

- If using a proxy or API gateway, confirm the forwarded headers and host are correct.
- If you see an OPTIONS preflight failing, verify the backend responds to OPTIONS and includes the required Access-Control-Allow-* headers.

If you can't change the backend, run the frontend and backend on the same origin (or use a dev proxy) as a workaround.

</details>

<details>
<summary><strong>LLM responses are slow or cause OOM errors</strong></summary>

This most likely means that either you are running the StudyBuddy backend on CPU, the models you chose don't fit on your VRAM, or your uploaded files are too large and the entire context does not fit on VRAM.

- Run ``nvidia-smi`` in a new terminal to verify if a GPU with CUDA support is available and how much VRAM is used/available.
- Consider using smaller models or less context if VRAM is too tight.

We are planning to drastically improve the VRAM handling and management of large/multiple files in the next update. Check the changelogs to see when this is available.

</details>

<details>
<summary><strong>How does StudyBuddy store uploaded files, conversations or notes? Is data persistent?</strong></summary>

Currently, StudyBuddy stores all uploaded and generated information locally in your browsers cache. The backend does not store anything. We are planning to switch to a more robust server side persistent storage in the next update.

</details>


<details>
<summary><strong>I get unexpected or low-quality answers from the model — can I improve them?</strong></summary>

The quality of the model answers is directly correlated to the performance and size of the used LLM model. Consider
switching to a more powerful text model.

If you are tight on VRAM, you can try to disable the image generation feature and use the saved VRAM for a better text model; or use an external API service (support coming soon)

</details>


<details>
<summary><strong>Is my data private and secure?</strong></summary>

StudyBuddy is designed for local use or self-deployment. It does not send or share any uploaded data beyond the connection between the frontend and backend.

By default, this connection is unencrypted and unauthenticated. If you deploy the frontend and backend on different machines, you should secure that connection. For example, by:

- Using HTTPS/TLS (e.g., via nginx and certbot)

- Setting up an SSH tunnel or VPN

- Restricting access with a firewall or IP allowlist

StudyBuddy does not currently implement built-in encryption, API keys, or remote authentication. If you host it remotely, make sure to protect it using your own network or application-layer security.

For local use, no special configuration is needed; everything runs on your own machine, and your data stays there.

We may add built-in security features for remote setups in future releases.

</details>

<details>
<summary><strong>Sometimes my generations fail!</strong></summary>

To generate flashcards and exams, StudyBuddy relies on structured output from large language models (LLMs).  
In some cases, the LLM might hallucinate or produce output that cannot be parsed correctly.  
This is more likely to happen with smaller or less capable models that struggle with structured output.

StudyBuddy includes multiple structuring and fallback mechanisms, but occasional failures can still occur.

- Try using a more powerful text model.
- If it only happens occasionally, simply rerun the generation.

</details>

<details>
<summary><strong>Can I trust StudyBuddy's output?</strong></summary>

StudyBuddy generates content based on the study materials you upload.  
Prompt design and low temperature settings help guide the models to stay as close as possible to your sources and factual information.

However, as with any large language model (LLM), occasional mistakes or inaccuracies can still occur; especially when using smaller or less capable models.  
If something looks wrong or suspicious, double-check it against your source material.

</details>

<details>
<summary><strong>Still stuck — where do I get help?</strong></summary>

- Open an issue in the repository with detailed troubleshooting information.
- Include environment (OS, Python/node versions), exact error messages, and the steps you've already tried.

Maintainers will triage in priority order; complete bug reports get faster responses.

</details>

