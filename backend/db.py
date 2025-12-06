# backend/db.py

import os
import json
import psycopg2
from typing import Optional, Tuple

# 🔌 Read Postgres URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Please configure it in your environment.")


def get_pg_conn():
    """Create a new connection to Postgres."""
    return psycopg2.connect(DATABASE_URL)


def init_db() -> None:
    """Create required tables if they don't exist."""
    with get_pg_conn() as conn:
        with conn.cursor() as cursor:
            # For mapping file_id -> user_name
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    file_id   TEXT PRIMARY KEY,
                    user_name TEXT
                )
                """
            )

            # For caching resume analysis by resume_hash
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS resumes (
                    resume_hash  TEXT PRIMARY KEY,
                    analysis_json TEXT,
                    model_name    TEXT,
                    created_at    TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )

            conn.commit()


# ---------- User name mapping (file_id -> user_name) ----------

def save_user_name(file_id: str, user_name: str) -> None:
    """Store or update user_name for a given file_id in Postgres."""
    with get_pg_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sessions (file_id, user_name)
                VALUES (%s, %s)
                ON CONFLICT (file_id) DO UPDATE
                SET user_name = EXCLUDED.user_name
                """,
                (file_id, user_name),
            )
            conn.commit()


def get_user_name(file_id: str) -> Optional[str]:
    """Fetch user_name for a given file_id from Postgres. Return None if not found."""
    with get_pg_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT user_name FROM sessions WHERE file_id = %s",
                (file_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else None


# ---------- Resume analysis caching (by resume_hash) ----------

def get_resume_analysis(resume_hash: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Return (analysis_obj, model_name) for a given resume_hash,
    or (None, None) if not cached.
    """
    with get_pg_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT analysis_json, model_name FROM resumes WHERE resume_hash = %s",
                (resume_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None, None
            analysis_json, model_name = row
            return json.loads(analysis_json), model_name


def save_resume_analysis(resume_hash: str, analysis_obj, model_name: Optional[str]) -> None:
    """
    Store analysis for a given resume_hash.
    analysis_obj is a Python dict/obj -> stored as JSON.
    """
    analysis_json = json.dumps(analysis_obj)
    with get_pg_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO resumes (resume_hash, analysis_json, model_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (resume_hash) DO UPDATE
                SET analysis_json = EXCLUDED.analysis_json,
                    model_name    = EXCLUDED.model_name
                """,
                (resume_hash, analysis_json, model_name),
            )
            conn.commit()
