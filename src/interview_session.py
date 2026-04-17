from dotenv import load_dotenv
import os
import json
from supabase import create_client

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)


def create_session(
    candidate_name: str,
    candidate_email: str,
    job_description: str,
    match_score: float,
    candidate_summary: str,
    matched_skills: list,
    missing_skills: list,
    questions: list
) -> str:
    """
    Creates a new interview session in Supabase.
    Returns the UUID session ID which becomes
    the unique part of the candidate's interview link.
    """
    record = {
        "candidate_name":    candidate_name,
        "candidate_email":   candidate_email,
        "job_description":   job_description,
        "match_score":       match_score,
        "questions":         json.dumps(questions),
        "answers":           json.dumps([]),
        "scores":            json.dumps([]),
        "final_report":      None,
        "status":            "pending",
        "candidate_summary": candidate_summary,
        "matched_skills":    json.dumps(matched_skills or []),
        "missing_skills":    json.dumps(missing_skills or [])
    }

    response = supabase.table("interview_sessions") \
        .insert(record).execute()

    session_id = response.data[0]["id"]
    print(f"Session created: {session_id}")
    return session_id


def load_session(session_id: str) -> dict:
    """
    Loads a session from Supabase by UUID.
    Returns the session dict with all fields parsed.
    Returns None if session not found.
    """
    response = supabase.table("interview_sessions") \
        .select("*") \
        .eq("id", session_id) \
        .execute()

    if not response.data:
        return None

    session = response.data[0]

    # Parse JSON fields safely
    for field in ["questions", "answers", "scores",
                  "matched_skills", "missing_skills"]:
        if isinstance(session.get(field), str):
            try:
                session[field] = json.loads(session[field])
            except (json.JSONDecodeError, TypeError):
                session[field] = []

    return session


def save_answer(
    session_id: str,
    answers: list,
    scores: list
):
    """
    Updates the session with the latest answers and scores.
    Called after each question is answered.
    """
    supabase.table("interview_sessions") \
        .update({
            "answers": json.dumps(answers),
            "scores":  json.dumps(scores),
            "status":  "in_progress"
        }) \
        .eq("id", session_id) \
        .execute()


def complete_session(
    session_id: str,
    answers: list,
    scores: list,
    final_report: str,
    decision: str,
    combined_score: float
):
    """
    Marks the session as complete and saves
    the final report and decision.
    Called after all questions are answered
    and the report is generated.
    """
    supabase.table("interview_sessions") \
        .update({
            "answers":       json.dumps(answers),
            "scores":        json.dumps(scores),
            "final_report":  final_report,
            "decision":      decision,
            "combined_score": combined_score,
            "status":        "completed"
        }) \
        .eq("id", session_id) \
        .execute()

    print(f"Session {session_id} completed. Decision: {decision}")


def get_all_sessions() -> list:
    """
    Returns all interview sessions ordered by
    creation date, newest first.
    Used by the hiring manager dashboard.
    """
    response = supabase.table("interview_sessions") \
        .select("*") \
        .order("created_at", desc=True) \
        .execute()

    sessions = response.data or []

    for session in sessions:
        for field in ["questions", "answers", "scores",
                      "matched_skills", "missing_skills"]:
            if isinstance(session.get(field), str):
                try:
                    session[field] = json.loads(session[field])
                except (json.JSONDecodeError, TypeError):
                    session[field] = []

    return sessions