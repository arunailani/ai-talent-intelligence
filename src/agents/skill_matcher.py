import os
import sys
import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Reuse the same model as store_resume.py and search_resumes.py
# Critical — must be identical model for consistent vector space
embedder = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

def cosine_similarity(vec1: list, vec2: list) -> float:
    """
    Computes cosine similarity between two vectors.
    Returns a value between 0 and 1.
    1.0 = identical meaning
    0.0 = completely unrelated meaning

    This is the same math Supabase uses internally
    with the <=> operator — we are just doing it in
    Python here for skill-level comparisons.
    """
    a = np.array(vec1)
    b = np.array(vec2)

    dot_product   = np.dot(a, b)
    magnitude_a   = np.linalg.norm(a)
    magnitude_b   = np.linalg.norm(b)

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return float(dot_product / (magnitude_a * magnitude_b))


def skill_is_present(
    required_skill: str,
    candidate_skills: list,
    threshold: float = 0.55,
    candidate_vectors: list = None
) -> bool:
    """
    Checks if a required skill is semantically present
    in the candidate's skill list.

    Instead of asking "does this string equal that string",
    we ask "does the meaning of this skill overlap
    sufficiently with any skill the candidate has?"

    Threshold of 0.55 means 55% semantic similarity
    is enough to count as a match. Tunable based on
    how strict you want the matching to be.

    Pass pre-cached candidate_vectors to avoid re-embedding
    the same candidate skills on every call (O(n+m) vs O(n×m)).

    Examples at threshold 0.55:
    "data visualization" vs "visualization (quicksight)" → ~0.78 → MATCH
    "stakeholder management" vs "project management"    → ~0.71 → MATCH
    "stakeholder management" vs "python"                → ~0.12 → NO MATCH
    "esg reporting" vs "data warehousing"               → ~0.18 → NO MATCH
    """
    required_vector = embedder.embed_query(required_skill)

    best_score = 0.0
    best_match = ""

    for i, candidate_skill in enumerate(candidate_skills):
        if candidate_vectors is not None:
            candidate_vector = candidate_vectors[i]
        else:
            candidate_vector = embedder.embed_query(candidate_skill)
        score = cosine_similarity(required_vector, candidate_vector)

        if score > best_score:
            best_score = score
            best_match = candidate_skill

    is_match = best_score >= threshold

    print(
        f"    '{required_skill}' vs best candidate match "
        f"'{best_match}' → {round(best_score * 100, 1)}% "
        f"→ {'MATCH' if is_match else 'NO MATCH'}"
    )

    return is_match


def match_skills_node(state: dict) -> dict:
    """
    Agent 3 — Skill Matcher (embedding-based)

    Now uses the same HuggingFace semantic embeddings
    as the rest of the pipeline — fully consistent
    architecture throughout.

    Each required skill is embedded and compared
    against all candidate skills using cosine similarity.
    This correctly handles:
    - Synonyms: "Data Visualization" ≈ "Visualization (Power BI)"
    - Inferred skills: "Stakeholder Management" ≈ "Project Management"
    - Abbreviations: "ML" ≈ "Machine Learning"
    - Varied phrasing: "team leadership" ≈ "led a team of 10"

    Candidate skill vectors are pre-cached once (O(n+m))
    rather than re-embedded per required skill (O(n×m)).

    Final score = required_match × 0.8 + preferred_match × 0.2
    """
    print("\n[Agent 3] Skill Matcher running (semantic mode)...")

    candidate_skills = state.get("candidate_skills") or []
    required_skills  = state.get("required_skills") or []
    preferred_skills = state.get("preferred_skills") or []

    if not required_skills:
        print("  No required skills found in JD")
        return {
            "matched_skills": [],
            "missing_skills": [],
            "match_score":    0.0
        }

    # Pre-cache candidate skill embeddings once — O(n) instead of re-embedding
    # on every required/preferred skill comparison (which would be O(n×m))
    candidate_vectors = (
        embedder.embed_documents(candidate_skills)
        if candidate_skills else []
    )

    print(f"\n  Checking {len(required_skills)} required skills "
          f"against {len(candidate_skills)} candidate skills:\n")

    matched = []
    missing = []

    for req_skill in required_skills:
        if skill_is_present(req_skill, candidate_skills,
                            candidate_vectors=candidate_vectors):
            matched.append(req_skill)
        else:
            missing.append(req_skill)

    # Check preferred skills — now contributes 20% to final score
    bonus = [
        pref for pref in preferred_skills
        if skill_is_present(pref, candidate_skills, threshold=0.55,
                            candidate_vectors=candidate_vectors)
    ]

    # 80/20 weighted score: required skills drive the decision,
    # preferred skills provide a meaningful but bounded boost
    required_match_score = round(len(matched) / len(required_skills) * 100, 1)

    if preferred_skills:
        preferred_match_score = round(
            len(bonus) / len(preferred_skills) * 100, 1
        )
    else:
        preferred_match_score = 0.0

    final_score = round(
        (required_match_score * 0.8) + (preferred_match_score * 0.2), 1
    )

    print(f"\n  Matched  : {matched}")
    print(f"  Missing  : {missing}")
    print(f"  Bonus    : {bonus}")
    print(f"  Required match : {required_match_score}%")
    print(f"  Preferred match: {preferred_match_score}%")
    print(f"  Final score    : {final_score}%")

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "match_score":    final_score
    }
