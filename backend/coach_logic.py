from typing import List,Dict
import json

from config import gemini_client, GENERATION_MODEL



def extract_name_from_resume(text: str) -> str:
    """
    Very simple heuristic: use the first non-empty line as name.
    You can improve this later with an LLM call if you want.
    """
    for line in text.split("\n"):
        line = line.strip()
        if line:
            return line
    return "there"

# cache so same resume text -> same analysis while server runs
_ANALYSIS_CACHE: Dict[int, Dict] = {}


def analyze_resume(text: str) -> Dict:
    """
    Use Gemini to generate structured analysis for the sidebar.
    LLM-only. No heuristics, no extra config – same style as generate_reply.
    """

    cache_key = hash(text)
    if cache_key in _ANALYSIS_CACHE:
        return _ANALYSIS_CACHE[cache_key]

    prompt = f"""
You are a senior career coach and resume expert.

Analyse the candidate's resume and return a SINGLE JSON object only.
DO NOT include any explanation, markdown, or backticks. ONLY raw JSON.

The JSON MUST have exactly this structure (field NAMES must match):

{{
  "overall_score": <integer 0-100>,
  "score_label": "<short human label, e.g. 'Strong IC, interview-ready'>",
  "top_skills": ["Skill1", "Skill2", "Skill3", "..."],

  "role_fit": [
    {{"role": "<job title 1>", "score": 0.0}},
    {{"role": "<job title 2>", "score": 0.0}},
    {{"role": "<job title 3>", "score": 0.0}}
  ],

  "experience_level": "<string like 'Junior', 'Mid-level (2–4 years)'>",
  "years_experience": <float number of years>,
  "project_count": <int>,
  "companies_count": <int>,

  "gaps": [
    "Short bullet about a weakness or missing element.",
    "Another realistic gap."
  ],

  "quick_wins": [
    "Actionable suggestion that can be done in 1–2 days.",
    "Another quick improvement."
  ]
}}

- Use these exact field names (snake_case) in the JSON.
- 'role_fit' should contain AT LEAST 5 realistic job titles, each with a 'score' in [0.0, 1.0].
- If something is not mentioned in the resume, use a reasonable default (0, 0.0, empty list, or "Unknown").
- Be honest but encouraging. Keep bullets short.

RESUME TEXT:
\"\"\"{text}\"\"\"
"""

    # IMPORTANT: call Gemini in the SAME WAY as generate_reply (no config)
    resp = gemini_client.models.generate_content(
        model=GENERATION_MODEL,
        contents=[prompt],
    )

    raw = (resp.text or "").strip()
    print("RAW ANALYSIS FROM GEMINI:\n", raw)

    # If LLM somehow returns nothing, fall back to a minimal safe structure
    if not raw:
        result = {
            "overall_score": None,
            "score_label": "",
            "top_skills": [],
            "role_fit": [],
            "experience_level": "",
            "years_experience": None,
            "project_count": None,
            "companies_count": None,
            "gaps": [],
            "quick_wins": [],
        }
        _ANALYSIS_CACHE[cache_key] = result
        return result

    # Try to isolate JSON if there is any extra text
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        raw_json = raw[start:end]
    except ValueError:
        raw_json = raw

    try:
        data = json.loads(raw_json)
    except Exception as e:
        print("❌ Failed to parse analysis JSON:", e)
        data = {}

    # small helper: support both snake_case and camelCase keys
    def get2(obj, snake, camel, default=None):
        return obj.get(snake) if snake in obj else obj.get(camel, default)

    result = {
        "overall_score": get2(data, "overall_score", "overallScore"),
        "score_label": get2(data, "score_label", "scoreLabel", ""),
        "top_skills": get2(data, "top_skills", "topSkills", []) or [],
        "role_fit": get2(data, "role_fit", "roleFit", []) or [],
        "experience_level": get2(data, "experience_level", "experienceLevel", ""),
        "years_experience": get2(data, "years_experience", "yearsExperience"),
        "project_count": get2(data, "project_count", "projectCount"),
        "companies_count": get2(data, "companies_count", "companiesCount"),
        "gaps": get2(data, "gaps", "gaps", []) or [],
        "quick_wins": get2(data, "quick_wins", "quickWins", []) or [],
    }

    _ANALYSIS_CACHE[cache_key] = result
    return result






def build_system_prompt(user_name: str) -> str:
    return f"""
You are a professional, friendly CAREER COACH.

You are talking to a candidate named {user_name}.
Your job is to:
- Help them explain their experience in very simple language.
- Help with STAR stories, interview answers, LinkedIn About, and resume bullets.
- Always stay on-topic: careers, interviews, communication, resumes, projects.

CRITICAL:
- You have access to their resume text.
- You must base your answers on their actual resume whenever relevant.
- Do NOT invent fake companies, projects, or tools that are not in the resume.
"""


def generate_reply(
    user_message: str,
    resume_chunks: List[str],
    coach_chunks: List[str],
    user_name: str,
) -> str:
    """
    Build a very explicit prompt that separates:
    - resume content
    - general coaching knowledge
    """

    resume_context = "\n\n".join(resume_chunks) if resume_chunks else "No resume context found."
    coach_context = "\n\n".join(coach_chunks) if coach_chunks else "No coach Q&A context found."

    system_prompt = build_system_prompt(user_name)

    prompt = f"""
SYSTEM INSTRUCTIONS:
{system_prompt}

<resume>
This is the candidate's resume content. Use this to understand their background,
projects, skills, and impact:

{resume_context}
</resume>

<coach_qa>
This is some general interview and career coaching knowledge you can use
for structure and best practices (STAR, 'Tell me about yourself', etc.):

{coach_context}
</coach_qa>

USER MESSAGE:
\"\"\"{user_message}\"\"\"

Now respond as their personal career coach.

Rules:
- Refer to specific things from their resume whenever possible.
- If they ask about their strengths, projects, STAR stories, etc., use resume details.
- If something is not in the resume, say you don't see it instead of guessing.
- Use simple, clear language, like a good communicator.

You MUST follow ALL of these rules:

1) Default: Provide a concise, medium-length answer only
   - About 2–4 short paragraphs or 5–8 bullet points.
   - Do NOT generate long, extended, or deeply detailed answers
     unless the user explicitly asks for a “long answer”,
     “detailed answer”, or “step-by-step explanation”.

2) RESPONSE FORMAT RULES (VERY IMPORTANT):

- NEVER write paragraph-style answers.
- ALWAYS break the entire answer into clear bullet points or numbered lists.
- Every idea must be a separate bullet point. No long chunks of text.
- Structure your response like this:

TITLE (ALL CAPS)

a) SECTION HEADER
- Bullet point 1
- Bullet point 2
- Bullet point 3

b) SECTION HEADER
- Bullet point 1
- Bullet point 2

c) SECTION HEADER
- Bullet point 1

- Do NOT write paragraphs.
- Do NOT write long-form narrative text.
- Keep every bullet point short, crisp, and direct.
- Do NOT use markdown symbols like **bold**, ## headings, or backticks.
- Use plain text only with hyphen bullets and numbered sections.


3) Absolutely NEVER:
   - Dump a big wall of text.
   - Ignore headings or bullet points.


"""

    resp = gemini_client.models.generate_content(
        model=GENERATION_MODEL,
        contents=[prompt],
    )
    return resp.text
