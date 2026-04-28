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

def _build_proctoring_js(session_id: str) -> str:
    """
    Proctoring JS — runs inside the st.components.v1.html() iframe.

    Navigation fix (root cause of all previous redirect failures):
      Previous code used '?session=...&terminated=true' — a relative
      URL starting with '?' is resolved against the iframe's base URL.
      For srcdoc iframes the base URL can be 'about:srcdoc', so the
      navigation went nowhere.  Now we use the absolute path
      '/interview?session=...&terminated=true' which works on any host
      (localhost, Streamlit Cloud, etc.) regardless of iframe origin.

    Three navigation fallbacks so one failure can't block everything:
      1. window.parent.location.href  (same-origin direct)
      2. window.top.location.href     (same-origin direct)
      3. <a target="_top"> click      (works even cross-origin)

    Guard: window._proctoringSetup on the iframe window (always
      writable). Streamlit reuses the same iframe when HTML content
      is unchanged, so this persists across reruns and prevents
      duplicate listeners.  Cleared automatically on full page reload.

    All window.parent access is wrapped in try/catch so a cross-origin
      SecurityError never silently kills the entire script.
    """
    return f"""
<script>
(function() {{
    // Guard — prevents duplicate listeners on Streamlit reruns.
    // Lives on the iframe window (always writable, no cross-origin issue).
    if (window._proctoringSetup) return;
    window._proctoringSetup = true;

    var store = window.sessionStorage;
    var SID   = "{session_id}";

    // Always reset — stale proc_done from a previous test in this tab
    // would otherwise silently block every termination attempt.
    store.setItem('proc_v', '0');
    store.removeItem('proc_done');
    store.removeItem('proc_t');

    function navigate() {{
        // Absolute path — resolves correctly on any host.
        // Relative '?...' fails when iframe base URL is about:srcdoc.
        var url = '/interview?session=' + SID + '&terminated=true';
        try {{ window.parent.location.href = url; }} catch(e) {{}}
        try {{ window.top.location.href    = url; }} catch(e) {{}}
        // Final fallback: anchor with target="_top" works cross-origin.
        var a = document.createElement('a');
        a.href = url; a.target = '_top';
        document.body.appendChild(a); a.click();
    }}

    function terminate(reason) {{
        if (store.getItem('proc_done') === '1') return;
        store.setItem('proc_done', '1');
        alert(
            'INTERVIEW TERMINATED.\\n\\n' + reason +
            '\\n\\nYour interview has been ended.' +
            ' Please contact your recruiter.'
        );
        navigate();
    }}

    function recordViolation(reason) {{
        var now  = Date.now();
        var last = parseInt(store.getItem('proc_t') || '0');
        if (now - last < 700) return;   // debounce — minimise fires both
        store.setItem('proc_t', now);   // blur + visibilitychange at once

        var v = parseInt(store.getItem('proc_v')) + 1;
        store.setItem('proc_v', v);
        if (v === 1) {{
            alert(
                'WARNING: ' + reason + '\\n\\n' +
                'This is your first warning. ' +
                'One more violation will immediately terminate your interview.'
            );
        }} else {{
            terminate(reason);
        }}
    }}

    // ── Tab switching ──────────────────────────────────────
    // visibilitychange fires on the iframe document when the browser
    // tab is hidden — confirmed to work from inside an iframe.
    document.addEventListener('visibilitychange', function() {{
        if (document.hidden) recordViolation('Tab switching detected.');
    }});

    // ── App / window switching ─────────────────────────────
    // Try parent window blur (fires when OS takes focus away).
    // If window.parent is cross-origin this throws — catch and fall
    // back to iframe window blur.
    try {{
        window.parent.addEventListener('blur', function() {{
            recordViolation('Application switching detected.');
        }});
    }} catch(e) {{
        window.addEventListener('blur', function() {{
            recordViolation('Application switching detected.');
        }});
    }}
}})();
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

# ── Proctoring termination check ─────────────────────────
# JS redirects here with &terminated=true on 2nd violation.
# Must be checked before loading session so the page never
# renders interview content after termination.
if params.get("terminated") == "true":
    st.title("Interview Terminated")
    st.error(
        "Your interview has been terminated due to "
        "tab switching or application switching violations.\n\n"
        "This decision is final and cannot be reversed.\n\n"
        "Please contact your recruiter for next steps."
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

# ── Inject proctoring JS ─────────────────────────────────
# Built here (not at module level) because session_id must be
# baked into the JS to avoid reading window.top.location.
# The one-time guard inside the JS ensures listeners are only
# ever registered once on window.top, even across reruns.
st.components.v1.html(_build_proctoring_js(session_id), height=0)

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