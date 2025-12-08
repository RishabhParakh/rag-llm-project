# RAGnarok – AI Resume & Interview Coach (RAG + Gemini + Pinecone)

> Transform your resume into insights and unforgettable stories.

RAGnarok is an AI-powered resume coach.  
Upload your resume (PDF) and chat with a coach that:

- Understands your **actual resume**
- Generates **STAR stories** and project explanations
- Suggests **role fit**, **gaps**, and **quick wins**
- Helps with **behavioral interview prep**, LinkedIn summary, and more

Under the hood it uses **Gemini**, **Pinecone**, and **Postgres (Supabase)** with a **FastAPI backend** and a **React + Vite frontend**.

---

## ✨ Features

- **Smart resume detection**
  - Detects whether an uploaded PDF *looks like* a resume using Gemini.
- **Structured resume analysis**
  - Gemini produces a JSON with:
    - `overall_score` (0–100) + `score_label`
    - `top_skills` (list)
    - `role_fit` (e.g. "Data Scientist", "MLE", etc. with scores)
    - `experience_level`, `years_experience`
    - `project_count`, `companies_count`
    - `gaps` and `quick_wins` (actionable suggestions)
- **RAG-powered coaching chat**
  - Uses **your resume chunks** + a curated **coach Q&A knowledge base** (`coach_qa.txt`).
  - Great for: STAR answers, "Tell me about yourself", project explanations, etc.
- **Caching to save LLM cost**
  - Computes a **SHA-256 hash** of the resume text.
  - Caches analysis in Postgres keyed by `resume_hash`.
  - Same resume → no extra Gemini calls.
- **Clean, modern UI**
  - Landing page for resume upload.
  - Chat page with:
    - Left: chat with markdown support.
    - Right: structured analysis cards and profile score.

---

## 🧱 Tech Stack

**Backend**

- Python 3.11
- FastAPI + Uvicorn
- Gemini (`google-genai`)
- Pinecone (serverless)
- Postgres (tested with Supabase) via `psycopg2`
- PyMuPDF (`pymupdf`) for PDF text extraction

**Frontend**

- React + Vite
- Axios
- React Markdown (`react-markdown` + `rehype-raw`)

**Infra**

- Docker / Docker Compose
- `.env` based configuration

---

## 📁 Project Structure

```text
rag-llm-project-main/
├─ backend/
│  ├─ main.py            # FastAPI app (upload + chat)
│  ├─ coach_logic.py     # Gemini prompts: name extraction, analysis, replies
│  ├─ coach_qa.txt       # Interview / coaching Q&A knowledge base
│  ├─ pdf_utils.py       # PDF text extraction + "is this a resume?" check
│  ├─ vector_store.py    # Embedding + Pinecone upsert/query helpers
│  ├─ schema.py          # Pydantic models for API
│  ├─ db.py              # Postgres (Supabase) cache + session storage
│  ├─ config.py          # Env loading, Gemini client, Pinecone setup
│  ├─ requirements.txt   # Backend dependencies
│  └─ Dockerfile
│
├─ frontend/
│  ├─ src/
│  │  ├─ App.jsx         # Main SPA: landing + chat views
│  │  ├─ App.css         # Global styles
│  │  ├─ landing.css     # Landing page styling
│  │  ├─ chat.css        # Chat layout & bubbles
│  │  ├─ main.jsx        # React entry point
│  │  └─ assets/...
│  ├─ index.html
│  ├─ package.json
│  └─ Dockerfile
│
├─ docker-compose.yml
└─ .gitignore
```

---

## ⚙️ Environment Variables

Create a `.env` file inside `backend/` (next to `main.py` and `config.py`):

```env
# === Required ===
GEMINI_API_KEY=your_gemini_api_key
PINECONE_API_KEY=your_pinecone_api_key

# Name of your Pinecone index
PINECONE_INDEX_NAME=rag-resume-coach

# Gemini models
EMBEDDING_MODEL=models/text-embedding-004
GENERATION_MODEL=gemini-2.5-flash

# Postgres (e.g., Supabase) connection string
DATABASE_URL=postgresql://user:password@hostname:5432/database

# Toggle DB usage (still need DATABASE_URL for import-time)
USE_DB=true
```

**✅ `config.py` will:**

- Load env vars via dotenv.
- Initialize Gemini + Pinecone client.
- Auto-create the Pinecone index if it does not exist.

On the frontend, you can configure the backend URL via `VITE_API_BASE`.
Either use `.env` in `frontend/`:

```env
VITE_API_BASE=http://localhost:8000
```

or rely on the default in `App.jsx` (`http://localhost:8000`).

---

## 🐳 Running with Docker Compose (Recommended)

From the repo root:

```bash
docker-compose up --build
```

This will:

- Build + run the backend on `http://localhost:8000`
- Build + run the frontend on `http://localhost:5173`

**Before running, make sure:**

- Your `.env` is correctly set up in `backend/`.
- Your Postgres / Supabase `DATABASE_URL` is valid and reachable.

Then open the app in your browser:

```
http://localhost:5173
```

For API docs:

```
http://localhost:8000/docs
```

---

## 🧪 Running Locally (Without Docker)

### 1. Backend (FastAPI)

```bash
cd backend

# (Optional but recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Set environment variables (or create `backend/.env` as shown above), then:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at `http://localhost:8000`.

### 2. Frontend (React + Vite)

```bash
cd frontend
npm install
```

Optional: create `frontend/.env`:

```env
VITE_API_BASE=http://localhost:8000
```

Then start the dev server:

```bash
npm run dev
```

Vite will show a URL like `http://localhost:5173`.

---

## 🧵 How It Works (High-Level Flow)

### Upload Resume

**Endpoint:** `POST /upload_resume`

**Accepts:** `multipart/form-data` with a file (PDF).

**Pipeline:**

1. Save the file under `backend/uploads/`.
2. Extract text via PyMuPDF (`pdf_utils.py`).
3. Use Gemini to decide if this looks like a resume.
4. Compute a `resume_hash` using SHA-256 of the text.
5. If seen before → load cached analysis from Postgres.
6. Otherwise:
   - Call Gemini with a strict JSON prompt (`analyze_resume` in `coach_logic.py`).
   - Store the JSON + model name into `resumes` table.
   - Chunk the text, embed via Gemini, and upsert vectors into Pinecone as `doc_type="resume_chunk"`.
7. Extract the first name from the resume (`extract_name_from_resume`) and store in `sessions` table keyed by `file_id`.

**Response (simplified):**

```json
{
  "file_id": "uuid",
  "greeting": "Hi Rishabh! I've analyzed your resume...",
  "analysis": {
    "overall_score": 78,
    "score_label": "Strong IC, interview-ready",
    "top_skills": ["Python", "ML", "RAG", "..."],
    "role_fit": [{ "role": "Data Scientist", "score": 0.83 }, "..."],
    "experience_level": "Mid-level (2–4 years)",
    "years_experience": 2.5,
    "project_count": 6,
    "companies_count": 3,
    "gaps": ["..."],
    "quick_wins": ["..."]
  }
}
```

### Chat with the Coach

**Endpoint:** `POST /chat`

**Body:**

```json
{
  "user_message": "Can you turn my Jio project into 2 STAR stories?",
  "file_id": "uuid-from-upload"
}
```

**Backend:**

1. Loads resume chunks from Pinecone filtered by this `file_id`.
2. Loads coach Q&A chunks (`doc_type="coach_qa"`) from `coach_qa.txt`.
3. Pulls `user_name` from `sessions` table (fallback to "friend" if missing).
4. Calls Gemini with:
   - User message
   - Retrieved resume + coach context
   - User's name
5. Returns a nicely formatted answer (often with bullet points / STAR structure).

**Response:**

```json
{ 
  "response": "Here are two STAR stories based on your Jio experience..." 
}
```

Frontend displays this in the chat UI with markdown rendering.

---

## 🗄️ Database Schema (Postgres)

`init_db()` in `db.py` creates two tables if they don't exist:

```sql
CREATE TABLE IF NOT EXISTS sessions (
  file_id   TEXT PRIMARY KEY,
  user_name TEXT
);

CREATE TABLE IF NOT EXISTS resumes (
  resume_hash   TEXT PRIMARY KEY,
  analysis_json TEXT,
  model_name    TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

- **sessions** – maps uploaded file IDs to first names.
- **resumes** – caches the LLM analysis JSON per unique resume.

---

## ✅ Status & Limitations

- Currently optimized for single PDF resume per session.
- Chat is turn-based and stateless on the backend (no long chat history stored).
- Requires:
  - Valid Gemini + Pinecone credentials.
  - A reachable Postgres instance for full functionality.

---
