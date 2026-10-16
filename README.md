# InterviewIQ-ML

Local resume-based interview practice. Resume text, matching, question generation, and answer scoring run through the local FastAPI service; no external AI service is called.

## Run locally

1. Install Python 3.10+ and Node.js 20+.
2. In PowerShell at the project root, create and activate the backend environment, then install dependencies:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python app.py
   ```

3. In a second terminal, start the frontend:

   ```powershell
   cd frontend
   npm install
   $env:VITE_API_BASE_URL = "http://127.0.0.1:8011"
   npm run dev
   ```

Open `http://localhost:5173`. The backend defaults to `http://127.0.0.1:8011` because 8010 may be reserved on some Windows machines. Set `PORT` before `python app.py` and `VITE_API_BASE_URL` before starting Vite if you need other ports. The FastAPI CORS allowlist defaults to the local Vite URLs and can be changed with `FRONTEND_ORIGINS`.

## Test the upload

Click **Use fictional sample PDF** in Resume Studio. It loads the bundled, selectable-text PDF at `frontend/public/sample-resume.pdf` and submits it through the same multipart `/resume/upload` endpoint used for a real resume. The sample is fictional test data. You can also select a PDF from any folder on your PC or drag it into the upload area. ChatGPT sandbox download links are not local Windows files; this sample removes that dependency.

## Run checks

From the project root, install the optional test dependencies and run the backend API tests:

```powershell
cd backend
pip install -r test-requirements.txt
python -m pytest -q
```

Then build the frontend from a second terminal:

```powershell
cd frontend
npm run build
```

## Interview flow

- Upload a text-based PDF resume (maximum 5 MB) to extract skills, education, projects, and experience.
- Generate up to 30 resume-related and general practice questions.
- Submit written answers for scoring, strengths, and targeted improvement prompts.
- Review the final average, per-question scores, and interview-wide practice recommendations; print or save the report as PDF.
- Optionally compare resume text with a job description using TF-IDF similarity and keyword coverage.

Question generation uses deterministic templates grounded in detected resume skills, project text, and experience; it is not LLM-level reasoning. Answer evaluation uses the compatible Random Forest artifact when available. This workspace has local model version `0.1.0`, verified against the nine current feature columns; the joblib file is ignored by Git. On a checkout without it, the API uses a clearly identified local TF-IDF and answer-structure heuristic, so the interview flow still works. To regenerate the artifact, run `python train.py` from `backend`. The labelled dataset has 15 examples and is illustrative; neither model nor fallback can verify technical correctness. Treat scores as practice signals, never hiring decisions. Scanned/image-only PDFs are not OCR processed; the app reports this and asks for a text-based PDF.
