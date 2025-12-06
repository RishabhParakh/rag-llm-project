import os
import uuid
import hashlib

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from .pdf_utils import extract_text_from_pdf, chunk_text, is_probable_resume
from .vector_store import embed_texts, upsert_vectors, seed_coach_qa_if_needed
from .coach_logic import extract_name_from_resume, generate_reply, analyze_resume
from .schema import ChatRequest, ChatResponse
from .config import PINECONE_DIMENSION

# ✅ DB helpers (Postgres via Supabase)
from .db import (
    init_db,
    save_user_name,
    get_user_name,
    get_resume_analysis,
    save_resume_analysis,
)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# CREATE uploads folder
UPLOAD_DIR = "backend/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
def startup_event():
    # Initialize DB tables (sessions, resumes)
    init_db()
    # Seed coach Q&A into Pinecone if needed
    seed_coach_qa_if_needed()


@app.post("/upload_resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    - Accept any uploaded file.
    - If it's a valid resume PDF:
        -> extract text
        -> compute resume_hash
        -> check DB cache (resumes table)
        -> if cached: reuse analysis, no LLM call
        -> if not cached: analyze with LLM, then store in DB
        -> chunk, embed, upsert to Pinecone as before
        -> store file_id -> user_name in Postgres (sessions table)
    - If it's not a valid resume (wrong format / random PDF / blank):
        -> do NOT upsert, but STILL return a file_id so UI can go to chat.
        -> Chat endpoint will later tell the user to upload a proper resume.
    """
    file_bytes = await file.read()
    file_id = str(uuid.uuid4())

    # Defaults
    greeting = "Hi there! I’ve loaded your file. Ask me anything to get started."
    analysis = None
    user_name = None

    is_pdf = file.filename.lower().endswith(".pdf")
    text = ""

    # Try to extract text only if PDF
    if is_pdf:
        try:
            text = extract_text_from_pdf(file_bytes)
        except Exception as e:
            print("⚠️ Error extracting PDF text:", e)
            text = ""

    # Decide if this is a "valid resume PDF"
    is_valid_resume = False
    if is_pdf and text.strip():
        try:
            is_valid_resume = is_probable_resume(text)
        except Exception as e:
            print("⚠️ Error in is_probable_resume:", e)
            is_valid_resume = False

    # 🔑 Compute a hash for this resume text (if we have text)
    resume_hash = None
    if text.strip():
        resume_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        print("🔑 Resume hash:", resume_hash)

    # ✅ Only upsert to Pinecone + analyze if it's a valid resume
    if is_valid_resume:
        # 1) Chunk + embed + upsert into Pinecone
        chunks = chunk_text(text)
        if chunks:
            vectors = embed_texts(chunks)
            if vectors:
                items = []
                for i, (vec, chunk) in enumerate(zip(vectors, chunks)):
                    items.append(
                        {
                            "id": f"{file_id}-{i}",
                            "values": vec,
                            "metadata": {
                                "file_id": file_id,
                                "text": chunk,
                                "doc_type": "resume_chunk",
                            },
                        }
                    )

                upsert_vectors(items)
                print("✅ UPSERTED RESUME CHUNKS:", len(items), "for file_id:", file_id)

        # 2) Extract user name + store in DB
        user_name = extract_name_from_resume(text) or "there"
        save_user_name(file_id, user_name)

        # 3) Check if this resume was analyzed before (cache)
        cached_analysis = None
        cached_model = None
        if resume_hash:
            cached_analysis, cached_model = get_resume_analysis(resume_hash)

        if cached_analysis is not None:
            # ✅ Use cached analysis – same resume, same result, no LLM call
            analysis = cached_analysis
            print("♻️ Using cached resume analysis for hash:", resume_hash)
        else:
            # ❌ Not cached yet – call LLM and then store
            analysis = analyze_resume(text)
            # if you want, track which LLM model you used:
            model_name = "resume-coach-llm"  # change to actual model name if you want
            if resume_hash:
                save_resume_analysis(resume_hash, analysis, model_name)
                print("💾 Saved new resume analysis for hash:", resume_hash)

        greeting = (
            f"Hi {user_name}! I’ve analyzed your resume. "
            "Ask me anything—STAR stories, interview prep, project explanations, LinkedIn summary—"
            "I'm your personal career coach now."
        )
    else:
        # Not a valid resume (non-PDF, random PDF, or unreadable PDF)
        print(
            f"⚠️ File {file.filename} (id={file_id}) is NOT detected as a valid resume. "
            "No Pinecone upsert performed."
        )
        greeting = (
            "Hi there! I’ve loaded your file. "
            "This isn’t a resume, please upload that next."
        )
        analysis = (
            "I could not detect this file as a proper resume. "
            "Please upload a clear resume PDF for best results."
        )

    # Always return a file_id so frontend can move to chat
    return {
        "file_id": file_id,
        "greeting": greeting,
        "analysis": analysis,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    from .vector_store import retrieve_texts

    # 1️⃣ No file_id at all -> user never uploaded anything
    if not payload.file_id:
        return ChatResponse(
            response="Please upload a valid resume in PDF format before we start chatting. 🙂"
        )

    # 2️⃣ Try to retrieve resume chunks ONLY for this file_id (no fallback)
    resume_chunks = retrieve_texts(
        query=payload.user_message,
        top_k=5,
        doc_types=["resume_chunk"],
        file_id=payload.file_id,
        allow_fallback=False,
    )

    # 3️⃣ If no chunks, uploaded file was not a valid resume
    if not resume_chunks:
        return ChatResponse(
            response=(
                "I couldn't find any valid resume content linked to this chat.\n\n"
                "👉 Please upload your actual resume in **PDF format** and then try asking your question again.\n"
                "Right now it looks like you might have uploaded a random or non-resume PDF. 🙂"
            )
        )

    # 4️⃣ Retrieve coach Q&A context (global, not per-resume)
    coach_chunks = retrieve_texts(
        query=payload.user_message,
        top_k=3,
        doc_types=["coach_qa"],
        file_id=None,
    )

    print("📄 RESUME CHUNKS FOUND:", len(resume_chunks))
    print("🎓 COACH CHUNKS FOUND:", len(coach_chunks))

    # 5️⃣ Get name from Postgres, else fall back to "friend"
    user_name1 = get_user_name(payload.file_id) or "friend"

    # 6️⃣ Generate the actual reply
    response = generate_reply(
        user_message=payload.user_message,
        resume_chunks=resume_chunks,
        coach_chunks=coach_chunks,
        user_name=user_name1,
    )

    return ChatResponse(response=response)
