from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from recruitment_pipeline import run_pipeline
from store_resume import store_resume
from interview_agent import generate_interview_questions
from interview_session import create_session, get_all_sessions, load_session

app = FastAPI(
    title="AI Talent Intelligence API",
    description="Resume screening and interview pipeline",
    version="1.0.0"
)

# Allow n8n and other tools to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# ── Health check ──────────────────────────────────────────
@app.get("/")
def health():
    """Quick check that the API is running."""
    return {
        "status": "running",
        "service": "AI Talent Intelligence API"
    }


# ── Screen a resume ───────────────────────────────────────
@app.post("/screen")
async def screen_resume(
    resume: UploadFile = File(...),
    job_description: str = Form(...),
    store_in_db: bool = Form(default=True)
):
    """
    Main screening endpoint called by n8n.

    Accepts a PDF resume and job description.
    Runs all 4 LangGraph agents.
    Returns structured screening results as JSON.

    n8n sends a multipart form request to this URL.
    The response JSON goes to the next n8n node.
    """
    if not resume.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted"
        )

    # Save uploaded file to temp path — agents need real path
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".pdf"
    ) as tmp:
        content = await resume.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = run_pipeline(tmp_path, job_description)

        if store_in_db:
            try:
                store_resume(tmp_path)
            except Exception as e:
                print(f"DB storage failed: {e}")

        return {
            "success":          True,
            "candidate_name":   result.get("candidate_name"),
            "candidate_email":  result.get("candidate_email"),
            "match_score":      result.get("match_score"),
            "recommendation":   result.get("recommendation"),
            "matched_skills":   result.get("matched_skills"),
            "missing_skills":   result.get("missing_skills"),
            "years_experience": result.get("years_experience"),
            "seniority_level":  result.get("seniority_level"),
            "final_report":     result.get("final_report"),
            "raw_summary":      result.get("raw_summary")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Generate interview link ───────────────────────────────
@app.post("/create-interview")
async def create_interview(
    candidate_name: str = Form(...),
    candidate_email: str = Form(default=""),
    job_description: str = Form(...),
    match_score: float = Form(...),
    candidate_summary: str = Form(default=""),
    matched_skills: str = Form(default="[]"),
    missing_skills: str = Form(default="[]")
):
    """
    Creates an interview session and returns
    the unique interview link.

    Called by n8n after screening — automatically
    generates and sends the link to the candidate.
    """
    import json

    try:
        matched = json.loads(matched_skills)
        missing = json.loads(missing_skills)
    except Exception:
        matched = []
        missing = []

    questions = generate_interview_questions(
        candidate_name=candidate_name,
        job_description=job_description,
        matched_skills=matched,
        missing_skills=missing,
        candidate_summary=candidate_summary,
        num_questions=5
    )

    session_id = create_session(
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        job_description=job_description,
        match_score=match_score,
        candidate_summary=candidate_summary,
        matched_skills=matched,
        missing_skills=missing,
        questions=questions
    )

    # In production this will be your deployed URL
    # For now it uses localhost
    interview_url = (
        f"http://localhost:8501/interview?session={session_id}"
    )

    return {
        "success":       True,
        "session_id":    session_id,
        "interview_url": interview_url,
        "candidate":     candidate_name,
        "email":         candidate_email
    }


# ── Get all sessions — for dashboard ─────────────────────
@app.get("/sessions")
def get_sessions():
    """Returns all interview sessions. Used by dashboard."""
    sessions = get_all_sessions()
    return {"sessions": sessions, "total": len(sessions)}


# ── Get single session ────────────────────────────────────
@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Returns a single session by ID."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session