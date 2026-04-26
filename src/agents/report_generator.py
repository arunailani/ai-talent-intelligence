from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
from rag_retriever import get_similar_candidates

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.3,
    max_retries=1
)


def generate_report_node(state: dict) -> dict:
    """
    Agent 4 — Report Generator (RAG-enhanced)

    Decision is calculated FIRST, then passed into
    the LLM prompt so the report text is always
    consistent with the recommendation badge.
    """
    print("\n[Agent 4] Report Generator running...")

    similar = get_similar_candidates(
        query=state.get("raw_summary", ""),
        top_k=2
    )

    similar_context = ""
    if similar:
        similar_context = "\n\nSimilar candidates in database:\n"
        for i, c in enumerate(similar, 1):
            skills_str = ", ".join(c.get("skills", [])) or "N/A"
            similar_context += (
                f"{i}. {c['name']} — {c['summary']} "
                f"Skills: {skills_str} "
                f"(similarity: {c['similarity']}%)\n"
            )

    # Calculate recommendation FIRST
    match_score = state.get("match_score") or 0
    recommendation = (
        "PROCEED TO INTERVIEW"
        if match_score >= 60
        else "NEEDS REVIEW"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a senior HR consultant
writing a structured hiring recommendation report.

CRITICAL: Your written text MUST be consistent with
and supportive of this recommendation: {recommendation}

If recommendation is PROCEED TO INTERVIEW:
Write positively. Acknowledge gaps as development areas.

If recommendation is NEEDS REVIEW:
Write constructively. Explain specific gaps clearly.

Be direct, specific, professional. Plain English.
Maximum 200 words. Reference similar candidates if provided."""),
        ("human", """Candidate     : {name}
Match Score   : {score}%
Matched Skills: {matched}
Missing Skills: {missing}
Seniority     : {seniority}
Summary       : {summary}
Recommendation: {recommendation}
{similar_context}

Write the hiring recommendation report now.
Your text must clearly support: {recommendation}""")
    ])

    chain = prompt | llm | StrOutputParser()

    report = chain.invoke({
        "name":           state.get("candidate_name", "Unknown"),
        "score":          match_score,
        "matched":        ", ".join(state.get("matched_skills") or []),
        "missing":        ", ".join(state.get("missing_skills") or []),
        "seniority":      state.get("seniority_level", "mid"),
        "summary":        state.get("raw_summary", ""),
        "recommendation": recommendation,
        "similar_context": similar_context
    })

    print(f"  Recommendation: {recommendation}")

    return {
        "final_report":   report.strip(),
        "recommendation": recommendation
    }