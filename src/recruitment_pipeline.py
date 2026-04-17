from langgraph.graph import StateGraph, END
from agents.state import RecruitmentState
from agents.resume_extractor import extract_resume_node
from agents.jd_analyzer import analyze_jd_node
from agents.skill_matcher import match_skills_node
from agents.report_generator import generate_report_node
from dotenv import load_dotenv
import os
import sys

sys.path.append(
    os.path.dirname(os.path.abspath(__file__))
)

load_dotenv()


def build_pipeline():
    """
    Constructs and compiles the LangGraph StateGraph.
    Called fresh for each pipeline run.
    """
    graph = StateGraph(RecruitmentState)

    graph.add_node("extract_resume",  extract_resume_node)
    graph.add_node("analyze_jd",      analyze_jd_node)
    graph.add_node("match_skills",    match_skills_node)
    graph.add_node("generate_report", generate_report_node)

    graph.set_entry_point("extract_resume")
    graph.add_edge("extract_resume",  "analyze_jd")
    graph.add_edge("analyze_jd",      "match_skills")
    graph.add_edge("match_skills",    "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


def run_pipeline(pdf_path: str, job_description: str) -> dict:
    """
    Main entry point for the pipeline.
    Called by both terminal and Streamlit UI.

    Returns the complete final state dictionary
    with all agent outputs populated.
    """
    pipeline = build_pipeline()

    initial_state = {
        "pdf_path":          pdf_path,
        "job_description":   job_description,
        "pdf_filename":      os.path.basename(pdf_path),
        "processing_status": "running",
        "candidate_name":    None,
        "candidate_email":   None,
        "candidate_skills":  None,
        "years_experience":  None,
        "raw_summary":       None,
        "required_skills":   None,
        "preferred_skills":  None,
        "seniority_level":   None,
        "matched_skills":    None,
        "missing_skills":    None,
        "match_score":       None,
        "final_report":      None,
        "recommendation":    None
    }

    final_state = pipeline.invoke(initial_state)
    final_state["processing_status"] = "complete"
    return final_state


# ── Terminal runner ────────────────────────────────────────
if __name__ == "__main__":

    JD = """
    Senior Data Analyst — ESG and Sustainability

    Required Skills: Python, SQL, Data Visualization,
    Stakeholder Management, ESG Reporting

    Preferred Skills: Hadoop, Spark, Tableau, Power BI

    We need a senior analyst with 5+ years experience
    in data analytics with ESG domain knowledge.
    """

    result = run_pipeline("data/sample_resume.pdf", JD)

    print("\n" + "=" * 55)
    print("FINAL REPORT")
    print("=" * 55)
    print(f"Candidate   : {result['candidate_name']}")
    print(f"Match Score : {result['match_score']}%")
    print(f"Decision    : {result['recommendation']}")
    print(f"\n{result['final_report']}")
    print("=" * 55)