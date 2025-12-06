import fitz  # PyMuPDF
from typing import List
import re
from dotenv import load_dotenv
import os
import textwrap
from google import genai
load_dotenv()

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    text = ""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        text += page.get_text()
    return text.strip()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks

# 🚀 NEW: simple heuristic to check if a PDF looks like a resume

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def is_probable_resume(text: str) -> bool:
    """
    Use Gemini to classify whether this text is a resume/CV.
    Returns True if LLM says it's a resume, False otherwise.
    """

    if not text:
        return False

    # Super-basic hard filters to avoid nonsense / giant books:
    if len(text) < 300:
        return False
    if len(text) > 60000:  # don't send huge reports/books to LLM
        return False

    # Optionally truncate to keep token usage low (keep start + end):
    max_chars = 12000
    if len(text) > max_chars:
        head = text[:8000]
        tail = text[-4000:]
        text_for_llm = head + "\n\n... [TRUNCATED] ...\n\n" + tail
    else:
        text_for_llm = text

    prompt = textwrap.dedent(f"""
    You are a strict document classifier.

    TASK:
    Decide if the following document is a **RESUME / CV** of a person.

    A resume typically:
    - lists contact info (name, email, phone, location)
    - has sections like: Summary, Education, Experience, Work Experience, Projects, Skills, Certifications, etc.
    - is 1–3 pages, mostly bullet points, short phrases.
    - describes multiple roles/positions with dates and responsibilities.

    It is NOT a resume if it looks like:
    - internship report, project report, thesis, dissertation
    - academic paper: has Abstract, Table of Contents, Chapter 1, Methodology, Literature Review, References, etc.
    - long narrative essay, book, or detailed technical report.

    VERY IMPORTANT:
    - Output EXACTLY one word: "YES" if it is a resume/CV, "NO" otherwise.
    - Do NOT output anything else.

    DOCUMENT START
    --------------------
    {text_for_llm}
    --------------------
    DOCUMENT END
    """)

    response = client.models.generate_content(
        model="gemini-2.5-flash",  # or whatever model you use
        contents=prompt,
    )

    raw = response.text.strip().upper()
    # Normalize in case Gemini says something like "YES, this is a resume."
    if "YES" in raw and "NO" not in raw:
        return True
    if "NO" in raw and "YES" not in raw:
        return False

    # Fallback: be conservative (treat as not resume)
    return False

