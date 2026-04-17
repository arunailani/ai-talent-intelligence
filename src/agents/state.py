from typing import TypedDict, Optional, List

class RecruitmentState(TypedDict):
    """
    Shared state passed between all 4 agents.
    Each agent reads from this and writes only
    its own output fields back.

    Two extra fields at the bottom support
    the Streamlit UI in Phase 3.
    """

    # ── Inputs ────────────────────────────────────
    pdf_path:           str
    job_description:    str

    # ── Agent 1 outputs — Resume Extractor ────────
    candidate_name:     Optional[str]
    candidate_email:    Optional[str]
    candidate_skills:   Optional[List[str]]
    years_experience:   Optional[int]
    raw_summary:        Optional[str]

    # ── Agent 2 outputs — JD Analyzer ─────────────
    required_skills:    Optional[List[str]]
    preferred_skills:   Optional[List[str]]
    seniority_level:    Optional[str]

    # ── Agent 3 outputs — Skill Matcher ───────────
    matched_skills:     Optional[List[str]]
    missing_skills:     Optional[List[str]]
    match_score:        Optional[float]

    # ── Agent 4 outputs — Report Generator ────────
    final_report:       Optional[str]
    recommendation:     Optional[str]

    # ── UI metadata — used by Streamlit only ──────
    pdf_filename:       Optional[str]
    processing_status:  Optional[str]