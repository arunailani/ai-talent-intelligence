import streamlit as st
import tempfile
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from recruitment_pipeline import run_pipeline
from store_resume import store_resume
from interview_agent import generate_interview_questions
from interview_session import create_session, get_all_sessions

# ── Page config ───────────────────────────────────────────
st.set_page_config(
    page_title="AI Talent Intelligence",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Navigation tabs ───────────────────────────────────────
tab_screen, tab_dashboard = st.tabs([
    "Resume Screening",
    "Interview Dashboard"
])

# ════════════════════════════════════════════════════════
# TAB 1 — RESUME SCREENING
# ════════════════════════════════════════════════════════
with tab_screen:

    st.title("AI Talent Intelligence Platform")
    st.caption(
        "LangGraph agents · Groq/Llama · "
        "HuggingFace embeddings · Supabase pgvector"
    )
    st.divider()

    left, right = st.columns([1, 1], gap="large")

    # ── Inputs ────────────────────────────────────────────
    with left:
        st.subheader("Inputs")

        uploaded_files = st.file_uploader(
            "Upload resume PDFs",
            type=["pdf"],
            accept_multiple_files=True
        )

        if uploaded_files:
            st.caption(
                f"{len(uploaded_files)} file(s): "
                + ", ".join([f.name for f in uploaded_files])
            )

        st.markdown("**Job Description**")
        job_description = st.text_area(
            label="jd",
            label_visibility="collapsed",
            placeholder=(
                "Paste the full job description here...\n\n"
                "Include:\n"
                "- Role title\n"
                "- Required skills\n"
                "- Preferred skills\n"
                "- Years of experience needed"
            ),
            height=250
        )

        store_in_db = st.checkbox(
            "Store in vector database",
            value=True
        )

        ready = bool(uploaded_files and job_description.strip())

        run_button = st.button(
            "Run Screening Pipeline",
            type="primary",
            disabled=not ready,
            use_container_width=True
        )

    # ── Results ───────────────────────────────────────────
    with right:
        st.subheader("Screening Results")

        if not run_button:
            st.info(
                "Upload resumes and enter a job description "
                "to begin screening."
            )

        if run_button and ready:

            all_results = []

            for uploaded_file in uploaded_files:
                st.markdown(
                    f"**Processing: {uploaded_file.name}**"
                )
                progress = st.progress(
                    0, text="Starting pipeline..."
                )

                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".pdf"
                ) as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name

                try:
                    progress.progress(
                        20, text="Running agents..."
                    )

                    with st.spinner(
                        f"Screening {uploaded_file.name}..."
                    ):
                        result = run_pipeline(
                            tmp_path, job_description
                        )

                    progress.progress(
                        80, text="Storing..."
                    )

                    if store_in_db:
                        try:
                            store_resume(tmp_path)
                        except Exception as e:
                            st.warning(f"DB storage failed: {e}")

                    progress.progress(100, text="Complete.")

                    all_results.append({
                        "filename": uploaded_file.name,
                        "result":   result
                    })

                except Exception as e:
                    st.error(
                        f"Error processing "
                        f"{uploaded_file.name}: {e}"
                    )
                    progress.empty()

                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

            # Store results in session state so they
            # persist after button interactions below
            st.session_state["screening_results"] = all_results
            st.session_state["jd_for_interview"] = job_description

        # ── Display results and interview link button ─────
        all_results = st.session_state.get(
            "screening_results", []
        )
        jd_stored = st.session_state.get(
            "jd_for_interview", job_description
            if 'job_description' in dir() else ""
        )

        if all_results:
            all_results.sort(
                key=lambda x: x["result"].get("match_score") or 0,
                reverse=True
            )

            st.divider()
            st.markdown(
                f"**{len(all_results)} candidate(s) screened "
                f"— ranked by match score**"
            )

            for rank, item in enumerate(all_results, 1):
                r        = item["result"]
                score    = r.get("match_score") or 0
                decision = r.get("recommendation", "NEEDS REVIEW")
                name     = r.get("candidate_name", "Unknown")

                with st.expander(
                    f"#{rank}  {name}  —  "
                    f"{score}%  |  {decision}",
                    expanded=(rank == 1)
                ):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Match Score", f"{score}%")
                    c2.metric(
                        "Experience",
                        f"{r.get('years_experience', 0)} yrs"
                    )
                    c3.metric(
                        "Seniority",
                        (r.get("seniority_level") or "—").title()
                    )
                    c4.metric("Decision", decision)

                    st.divider()

                    sk1, sk2 = st.columns(2)
                    with sk1:
                        st.markdown("**Matched skills**")
                        for s in (r.get("matched_skills") or []):
                            st.success(s)

                    with sk2:
                        st.markdown("**Missing skills**")
                        for s in (r.get("missing_skills") or []):
                            st.warning(s)

                    st.divider()
                    st.markdown("**Screening Report**")
                    st.write(
                        r.get("final_report", "No report.")
                    )

                    # ── Generate Interview Link ────────────
                    st.divider()
                    st.markdown("**Send for Interview**")

                    btn_key = f"gen_link_{rank}_{name}"

                    if st.button(
                        f"Generate Interview Link for {name}",
                        key=btn_key,
                        use_container_width=True
                    ):
                        with st.spinner(
                            "Generating interview questions..."
                        ):
                            questions = generate_interview_questions(
                                candidate_name=name,
                                job_description=jd_stored,
                                matched_skills=(
                                    r.get("matched_skills") or []
                                ),
                                missing_skills=(
                                    r.get("missing_skills") or []
                                ),
                                candidate_summary=(
                                    r.get("raw_summary") or ""
                                ),
                                num_questions=5
                            )

                        session_id = create_session(
                            candidate_name=name,
                            candidate_email=(
                                r.get("candidate_email") or ""
                            ),
                            job_description=jd_stored,
                            match_score=score,
                            candidate_summary=(
                                r.get("raw_summary") or ""
                            ),
                            matched_skills=(
                                r.get("matched_skills") or []
                            ),
                            missing_skills=(
                                r.get("missing_skills") or []
                            ),
                            questions=questions
                        )

                        interview_url = (
                            f"http://localhost:8501/interview"
                            f"?session={session_id}"
                        )

                        st.success("Interview link generated!")
                        st.code(interview_url)
                        st.caption(
                            "Copy this link and send it "
                            f"to {name} via email or WhatsApp. "
                            "They can take the interview "
                            "from any browser."
                        )

                    with st.expander("Candidate details"):
                        st.markdown(
                            f"**Email:** "
                            f"{r.get('candidate_email', 'Not found')}"
                        )
                        st.markdown("**Extracted skills:**")
                        skills = r.get("candidate_skills") or []
                        if skills:
                            st.write(", ".join(skills))
                        st.markdown("**Summary:**")
                        st.write(r.get("raw_summary", ""))


# ════════════════════════════════════════════════════════
# TAB 2 — INTERVIEW DASHBOARD
# ════════════════════════════════════════════════════════
with tab_dashboard:

    st.title("Interview Dashboard")
    st.caption("Track all candidate interviews and results")
    st.divider()

    if st.button("Refresh", use_container_width=False):
        st.rerun()

    sessions = get_all_sessions()

    if not sessions:
        st.info(
            "No interviews generated yet. "
            "Screen a resume and generate an interview link first."
        )
    else:
        # Summary metrics
        total     = len(sessions)
        pending   = sum(
            1 for s in sessions if s.get("status") == "pending"
        )
        progress_count = sum(
            1 for s in sessions
            if s.get("status") == "in_progress"
        )
        completed = sum(
            1 for s in sessions if s.get("status") == "completed"
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Interviews", total)
        m2.metric("Pending", pending)
        m3.metric("In Progress", progress_count)
        m4.metric("Completed", completed)

        st.divider()

        for session in sessions:
            status    = session.get("status", "pending")
            name      = session.get("candidate_name", "Unknown")
            score     = session.get("match_score", 0)
            combined  = session.get("combined_score")
            decision  = session.get("decision", "")

            # Status badge
            status_labels = {
                "pending":     "Awaiting Candidate",
                "in_progress": "Interview In Progress",
                "completed":   "Completed"
            }
            label = status_labels.get(status, status.title())

            with st.expander(
                f"{name}  —  Resume: {score}%  |  {label}",
                expanded=(status == "completed")
            ):
                d1, d2, d3 = st.columns(3)
                d1.metric("Resume Match", f"{score}%")

                if combined:
                    d2.metric(
                        "Combined Score", f"{combined}%"
                    )
                else:
                    d2.metric("Combined Score", "Pending")

                d3.metric(
                    "Decision",
                    decision if decision else "Pending"
                )

                # Show interview link if still pending
                if status == "pending":
                    session_id = session.get("id")
                    interview_url = (
                        f"http://localhost:8501/interview"
                        f"?session={session_id}"
                    )
                    st.markdown("**Interview Link:**")
                    st.code(interview_url)

                # Show full report if completed
                if status == "completed":
                    answers   = session.get("answers", [])
                    questions = session.get("questions", [])
                    scores    = session.get("scores", [])

                    if questions:
                        st.markdown("**Interview Q&A:**")
                        for i, (q, a, s) in enumerate(
                            zip(questions, answers, scores), 1
                        ):
                            st.markdown(
                                f"**Q{i}:** {q['question']}"
                            )
                            st.write(f"**Answer:** {a}")
                            sc = s.get("score", 0)
                            fb = s.get("feedback", "")
                            st.caption(
                                f"Score: {sc}/10 — {fb}"
                            )
                            st.divider()

                    st.markdown("**Final Report:**")
                    st.write(
                        session.get(
                            "final_report", "No report yet."
                        )
                    )

# ── Footer ────────────────────────────────────────────────
st.divider()
st.caption(
    "AI Talent Intelligence Platform  ·  Phase 3  ·  "
    "LangGraph + LangChain + Groq + HuggingFace + Supabase"
)