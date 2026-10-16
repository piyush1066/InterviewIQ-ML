# InterviewIQ-ML 🚀

### Resume-Based Interview Practice & ML-Powered Answer Evaluation

**Live Demo:** [interviewiq-ml-1.onrender.com](https://interviewiq-ml-1.onrender.com)

InterviewIQ-ML is a web application that helps candidates prepare for interviews using their resumes. It extracts relevant information from PDF resumes, generates personalized practice questions, evaluates written answers, and compares resumes with job descriptions using machine learning and natural language processing techniques.

The application combines a React frontend with a Python FastAPI backend, providing a complete workflow for resume analysis and interview practice without relying on external generative AI APIs.

## ✨ Features

- **Resume Parsing:** Upload a PDF resume to extract text, technical skills, education, projects, and experience.
- **Personalized Interview Questions:** Generate up to 30 interview questions based on the candidate's resume, detected skills, projects, and experience.
- **Answer Evaluation:** Receive a score out of 10, strengths, and actionable feedback on relevance, completeness, and answer structure.
- **ML-Based Scoring:** Use a trained Random Forest model for additional score calibration when a reference answer is available.
- **Resume–Job Matching:** Compare a resume with a job description using TF-IDF similarity and keyword overlap.
- **Skill Gap Identification:** Review matched and missing terms to identify areas for improvement.
- **Interview Practice Reports:** Review individual answers, scores, and improvement suggestions.
- **Sample Resume:** Try the application using the built-in fictional sample PDF.
- **Local-First Processing:** Resume extraction, question generation, matching, and evaluation run through the application's backend without external AI API calls.

## 🛠️ Tech Stack

| Component | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript, CSS |
| Backend | Python, FastAPI, Uvicorn |
| Machine Learning | scikit-learn, Random Forest, TF-IDF |
| Text Analysis | Cosine similarity, keyword overlap, text-based features |
| PDF Processing | pypdf |
| Data Processing | pandas, NumPy |
| Model Serialization | joblib |
| Deployment | Render |

## 🏗️ Architecture

```text
                    Candidate
                       |
                       v
              React + Vite Frontend
                       |
                 HTTP Requests
                       |
                       v
                FastAPI Backend
                       |
          +------------+------------+
          |            |            |
          v            v            v
      Resume       Interview      Resume–Job
      Parsing      Questions       Matching
          |            |            |
          +------------+------------+
                       |
                       v
                Answer Evaluation
                       |
              +--------+--------+
              |                 |
              v                 v
         Text Evidence     Random Forest
         & Relevance       Calibration
              |                 |
              +--------+--------+
                       |
                       v
              Scores & Feedback
```

## 🌐 Live Demo

Try InterviewIQ-ML here:

**[Launch InterviewIQ-ML →](https://interviewiq-ml-1.onrender.com)**

1. Open the application.
2. Upload your resume or select the built-in sample PDF.
3. Generate interview questions based on your resume.
4. Submit answers and review scores and feedback.
5. Compare your resume against a target job description.

## 💻 Run Locally

### Prerequisites

- Python 3.10 or later
- Node.js and npm
- Git (optional)

### 1. Clone or download the project

```bash
git clone <your-github-repository-url>
cd InterviewIQ-ML
```

If you downloaded the ZIP, extract it and open a terminal in the project folder.

### 2. Start the backend

Open a terminal and run:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8011 --reload
```

The backend will run at:

- API: `http://127.0.0.1:8011`
- Interactive API documentation: `http://127.0.0.1:8011/docs`
- Health check: `http://127.0.0.1:8011/health`

### 3. Start the frontend

Open a second terminal from the project root:

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL = "http://127.0.0.1:8011"
npm run dev
```

Open the local URL displayed by Vite, usually `http://localhost:5173`.

### 4. Configure environment variables

The backend supports these environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `HOST` | Backend host | `127.0.0.1` |
| `PORT` | Backend port | `8011` |
| `MAX_TEXT_CHARS` | Maximum text length | `30000` |
| `MAX_PDF_BYTES` | Maximum PDF size | `5242880` bytes |
| `FRONTEND_ORIGINS` | Allowed frontend origins for CORS | Local Vite origins |

For the frontend, configure `VITE_API_BASE_URL` with the backend's base URL. Do not append `/health` or another API route.

Use the provided `.env.example` files as templates. Keep actual `.env` files out of Git.

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Check backend health and model availability |
| POST | `/resume/upload` | Upload and parse a PDF resume |
| POST | `/interview/generate` | Generate interview questions |
| POST | `/answer/evaluate` | Evaluate a candidate's written answer |
| POST | `/resume/match` | Compare resume text with a job description |

Interactive documentation is available at `/docs` when the backend is running.

## ☁️ Deployment on Render

The frontend and backend are deployed as separate services.

### Backend — Web Service

- **Root Directory:** `backend`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`

Configure `FRONTEND_ORIGINS` with the exact deployed frontend URL.

Ensure `backend/artifacts/answer_scorer.joblib` is included in the deployed source if the trained model is required.

Verify the backend using `/health`. A successful response includes `"status": "ok"`.

### Frontend — Static Site

- **Root Directory:** `frontend`
- **Build Command:** `npm ci && npm run build`
- **Publish Directory:** `dist`
- **Environment Variable:** `VITE_API_BASE_URL` set to the deployed backend URL.

After changing `VITE_API_BASE_URL`, trigger a new frontend build.

## 🧪 Testing

Backend tests are available in `backend/tests/`.

Run them with:

```powershell
cd backend
pip install -r requirements.txt
pip install -r test-requirements.txt
python -m pytest -q
```

Build the frontend to verify the production bundle:

```powershell
cd frontend
npm ci
npm run build
```

## 📁 Project Structure

```text
InterviewIQ-ML/
├── backend/
│   ├── artifacts/
│   │   └── answer_scorer.joblib
│   ├── data/
│   │   └── answer_training.csv
│   ├── tests/
│   ├── app.py
│   ├── ml_features.py
│   ├── train.py
│   ├── requirements.txt
│   └── test-requirements.txt
├── frontend/
│   ├── public/
│   │   └── sample-resume.pdf
│   ├── src/
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
└── README.md
```

## ⚠️ Limitations

- Only text-based PDFs are supported. Scanned PDFs and image-only documents are not processed with OCR.
- The maximum PDF upload size is 5 MB by default.
- Interview questions use deterministic templates rather than an LLM.
- Resume matching uses text similarity and keyword overlap; it does not guarantee job suitability.
- The answer-scoring dataset contains only 15 illustrative examples. The trained model and scoring heuristics are experimental and have not been established as reliable measures of technical correctness.
- Scores should be used as interview-practice guidance, not as the sole basis for hiring decisions.

## 🔒 Privacy

Resume content is sent to the configured backend for processing. Use only documents you have permission to process. Never commit private resumes, actual `.env` files, or credentials to a public repository.

## 🎯 Project Goal

InterviewIQ-ML demonstrates how machine learning, text processing, PDF extraction, and full-stack development can be combined to build a practical interview-preparation application.

---

**Built with React, FastAPI, and machine learning.**
