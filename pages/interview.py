import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "src"
))

from interview_session import (
    load_session, save_answer, complete_session
)
from interview_agent import score_answer, generate_interview_report

st.set_page_config(
    page_title="AI Interview",
    page_icon="🎯",
    layout="centered"
)

# ── Proctoring JavaScript ─────────────────────────────────
# Injects browser-level tab visibility detection.
# When candidate switches tabs or minimises window,
# the browser fires a visibilitychange event.
# We count violations and terminate after 2 warnings.

PROCTORING_JS = """
<script>
// Initialise violation counter in sessionStorage
// so it persists across Streamlit reruns
if (!sessionStorage.getItem('violations')) {
    sessionStorage.setItem('violations', '0');
}
if (!sessionStorage.getItem('terminated')) {
    sessionStorage.setItem('terminated', 'false');
}

document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        var violations = parseInt(
            sessionStorage.getItem('violations')
        ) + 1;
        sessionStorage.setItem('violations', violations);

        if (violations === 1) {
            alert(
                'WARNING: Tab switching detected.\\n\\n' +
                'This is your first warning.\\n' +
                'Switching tabs again will terminate ' +
                'your interview immediately.'
            );
        } else if (violations >= 2) {
            sessionStorage.setItem('terminated', 'true');
            alert(
                'INTERVIEW TERMINATED.\\n\\n' +
                'You switched tabs more than once.\\n' +
                'Your interview has been ended. ' +
                'Please contact your recruiter.'
            );
            // Force page reload to show termination screen
            window.location.reload();
        }
    }
});

// Also detect window blur — catches switching to
// other applications like Word or Calculator
var blurCount = 0;
window.addEventListener('blur', function() {
    blurCount++;
    if (blurCount > 1) {
        var violations = parseInt(
            sessionStorage.getItem('violations')
        ) + 1;
        sessionStorage.setItem('violations', violations);
        if (violations >= 2) {
            sessionStorage.setItem('terminated', 'true');
            alert(
                'INTERVIEW TERMINATED.\\n\\n' +
                'Application switching detected.\\n' +
                'Your interview has been ended.'
            );
            window.location.reload();
        }
    }
});

// Check termination status on every page load
window.addEventListener('load', function() {
    if (sessionStorage.getItem('terminated') === 'true') {
        document.body.innerHTML =
            '<div style="text-align:center;padding:60px;">' +
            '<h1>Interview Terminated</h1>' +
            '<p>Your interview was terminated due to ' +
            'tab switching violations.</p>' +
            '<p>Please contact your recruiter.</p>' +
            '</div>';
    }
});
</script>
"""

# ── Read session ID from URL ──────────────────────────────
params = st.query_params
session_id = params.get("session", None)

if not session_id:
    st.error(
        "Invalid interview link. "
        "Please contact your recruiter for the correct link."
    )
    st.stop()

# ── Load session from Supabase ────────────────────────────
session = load_session(session_id)

if not session:
    st.error(
        "Session not found. "
        "This link may be invalid or expired."
    )
    st.stop()

# ── Already completed ─────────────────────────────────────
if session.get("status") == "completed":
    st.title("Interview Complete")
    st.success(
        f"Thank you {session['candidate_name']}. "
        "Your interview has been submitted successfully."
    )
    st.info(
        "The hiring team will review your responses "
        "and contact you with next steps."
    )
    st.stop()

# ── Session data ──────────────────────────────────────────
candidate_name    = session["candidate_name"]
job_description   = session["job_description"]
candidate_summary = session.get("candidate_summary", "")
match_score       = session.get("match_score", 0)
questions         = session.get("questions", [])
existing_answers  = session.get("answers", [])
existing_scores   = session.get("scores", [])
total_questions   = len(questions)

# ── Initialise Streamlit session state ────────────────────
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False

if "answers" not in st.session_state:
    st.session_state.answers = list(existing_answers)

if "scores" not in st.session_state:
    st.session_state.scores = list(existing_scores)

if "current_q" not in st.session_state:
    st.session_state.current_q = len(st.session_state.answers)

if "interview_complete" not in st.session_state:
    st.session_state.interview_complete = (
        len(st.session_state.answers) >= total_questions
    )

if "terminated" not in st.session_state:
    st.session_state.terminated = False

# ── Inject proctoring JS on every page ───────────────────
st.components.v1.html(PROCTORING_JS, height=0)

# ════════════════════════════════════════════════════════
# SCREEN 1 — WELCOME PAGE (before interview starts)
# ════════════════════════════════════════════════════════
if not st.session_state.interview_started:

    # Header
    st.title("Welcome to Your Interview")
    st.markdown(
        f"### Hello, {candidate_name}"
    )
    st.caption(
        "AI Talent Intelligence Platform — "
        "Powered by LangGraph and Groq/Llama"
    )
    st.divider()

    # Role info
    st.markdown("**You are interviewing for:**")
    st.info(job_description[:250] + "...")

    st.divider()

    # Instructions
    st.markdown("### Before you begin — please read carefully")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Interview format**")
        st.markdown(
            f"- {total_questions} questions total\n"
            "- One question at a time\n"
            "- Text-based answers\n"
            "- No time limit per question\n"
            "- Cannot go back to previous answers"
        )

    with col2:
        st.markdown("**Tips for strong answers**")
        st.markdown(
            "- Use specific examples from your experience\n"
            "- Structure answers: Situation → Action → Result\n"
            "- Aim for 3-5 sentences minimum per answer\n"
            "- Be honest — vague answers score lower\n"
            "- Read each question fully before answering"
        )

    st.divider()

    # Proctoring rules — shown prominently
    st.markdown("### Proctoring rules")

    st.error(
        "**This interview is proctored. Please read these rules:**\n\n"
        "1. Do NOT switch to another browser tab during the interview\n"
        "2. Do NOT switch to another application (Word, Chrome, etc.)\n"
        "3. Do NOT minimise this window\n\n"
        "**First violation:** Warning popup — interview continues\n"
        "**Second violation:** Interview terminated immediately\n\n"
        "Termination is final and cannot be reversed."
    )

    st.divider()

    # Confirmation checkbox — candidate must acknowledge
    confirmed = st.checkbox(
        "I have read and understood the instructions "
        "and proctoring rules above"
    )

    start_button = st.button(
        "Start Interview",
        type="primary",
        disabled=not confirmed,
        use_container_width=True
    )

    if not confirmed:
        st.caption(
            "Please tick the checkbox above to enable "
            "the Start Interview button."
        )

    if start_button and confirmed:
        st.session_state.interview_started = True
        st.rerun()

# ════════════════════════════════════════════════════════
# SCREEN 2 — ACTIVE INTERVIEW
# ════════════════════════════════════════════════════════
elif not st.session_state.interview_complete:

    answered      = len(st.session_state.answers)
    current_index = st.session_state.current_q

    # Progress bar
    st.progress(
        answered / total_questions,
        text=f"Question {answered + 1} of {total_questions}"
    )

    st.markdown(" ")

    # Show previous answers collapsed
    if st.session_state.answers:
        with st.expander(
            f"Your previous answers ({answered} completed)",
            expanded=False
        ):
            for i, (prev_q, prev_a) in enumerate(
                zip(
                    questions[:answered],
                    st.session_state.answers
                ), 1
            ):
                st.markdown(f"**Q{i}:** {prev_q['question']}")
                st.write(prev_a)
                score_data = (
                    st.session_state.scores[i-1]
                    if i-1 < len(st.session_state.scores)
                    else {}
                )
                if score_data:
                    st.caption(
                        f"Score: {score_data.get('score', 0)}/10"
                    )
                st.divider()

    # Current question
    if current_index < total_questions:
        current_q = questions[current_index]

        col_heading, col_badge = st.columns([5, 1])
        with col_heading:
            st.markdown(
                f"### Question {current_index + 1} "
                f"of {total_questions}"
            )
        with col_badge:
            difficulty = current_q.get("difficulty", "medium")
            if difficulty == "easy":
                st.success("EASY")
            elif difficulty == "hard":
                st.error("HARD")
            else:
                st.warning("MEDIUM")

        st.caption(
            f"Testing: {current_q.get('competency', '')}"
        )

        st.markdown(" ")
        st.info(f"**{current_q['question']}**")
        st.markdown(" ")

        st.caption(
            "Be specific. Use real examples. "
            "Aim for 3-5 sentences minimum."
        )

        answer_key = f"answer_input_{current_index}"
        answer = st.text_area(
            label="Your answer",
            label_visibility="collapsed",
            placeholder=(
                "Type your answer here...\n\n"
                "Example structure:\n"
                "Situation: describe the context\n"
                "Action: what you specifically did\n"
                "Result: the outcome and impact"
            ),
            height=220,
            key=answer_key
        )

        st.markdown(" ")

        is_last = current_index == total_questions - 1
        btn_label = (
            "Submit Answer & Continue →"
            if not is_last
            else "Submit Final Answer"
        )

        answer_valid = answer and len(answer.strip()) >= 30

        if st.button(
            btn_label,
            type="primary",
            use_container_width=True,
            disabled=not answer_valid
        ):
            with st.spinner("Evaluating your answer..."):
                score_data = score_answer(
                    question=current_q,
                    answer=answer,
                    job_description=job_description,
                    candidate_summary=candidate_summary
                )

            st.session_state.answers.append(answer)
            st.session_state.scores.append(score_data)

            save_answer(
                session_id=session_id,
                answers=st.session_state.answers,
                scores=st.session_state.scores
            )

            st.session_state.current_q += 1

            if st.session_state.current_q >= total_questions:
                st.session_state.interview_complete = True

            st.rerun()

        if not answer_valid:
            st.caption(
                "Button enables once you have typed "
                "at least a few sentences (30+ characters)."
            )

# ════════════════════════════════════════════════════════
# SCREEN 3 — ALL QUESTIONS ANSWERED — SUBMIT
# ════════════════════════════════════════════════════════
else:

    st.title("All Questions Answered")
    st.success(
        f"You have completed all {total_questions} questions."
    )

    st.info(
        "Click Submit Interview below to finalise. "
        "Once submitted you cannot change your answers."
    )

    st.markdown(" ")

    if st.button(
        "Submit Interview",
        type="primary",
        use_container_width=True
    ):
        with st.spinner(
            "Generating your interview report... "
            "this takes about 15 seconds."
        ):
            report_data = generate_interview_report(
                candidate_name=candidate_name,
                questions=questions,
                answers=st.session_state.answers,
                scores=st.session_state.scores,
                match_score=match_score,
                job_description=job_description
            )

        complete_session(
            session_id=session_id,
            answers=st.session_state.answers,
            scores=st.session_state.scores,
            final_report=report_data["report"],
            decision=report_data["decision"],
            combined_score=report_data["combined_score"]
        )

        st.rerun()