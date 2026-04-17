from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import json
import os

load_dotenv()

# Two LLM instances —
# llm_strict for structured JSON output (temperature=0)
# llm for natural language reports (temperature=0.3)
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.3,
    max_retries=1
)

llm_strict = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_retries=1
)


# ── Question Generation ───────────────────────────────────

def generate_interview_questions(
    candidate_name: str,
    job_description: str,
    matched_skills: list,
    missing_skills: list,
    candidate_summary: str,
    num_questions: int = 5
) -> list:
    """
    Generates targeted interview questions based on:
    - The job description requirements
    - Skills the candidate has (probe depth of knowledge)
    - Skills the candidate lacks (probe learning potential)
    - The candidate's background summary

    Returns a list of question dicts, each with:
    id, question text, competency tested, question type
    """
    print(f"\n[Interview Agent] Generating {num_questions} questions...")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a senior technical interviewer.
Generate exactly {num_questions} interview questions
for this specific candidate and role.

Rules:
1. Mix question types across the {num_questions} questions:
   - At least 2 technical questions testing matched skills
   - At least 1 situational question about a missing skill
   - At least 1 behavioural question about past experience
   - At least 1 role-fit question about this specific job

2. Make questions specific to THIS candidate and THIS role.
   Reference their actual background where relevant.
   Do not use generic interview questions.

3. Each question should require a 2-3 minute verbal answer.
   Not too easy, not impossibly hard.

4. Return ONLY a valid JSON array. No markdown. No extra text.
   Exactly this structure:
[
  {{
    "id": 1,
    "question": "the full question text here",
    "competency": "what skill or trait this tests",
    "type": "technical"
  }},
  {{
    "id": 2,
    "question": "the full question text here",
    "competency": "what skill or trait this tests",
    "type": "behavioural"
  }}
]

Valid types: technical, situational, behavioural, role-fit
Pure JSON array only. Nothing else."""),
        ("human", """Candidate name  : {name}
Role            : {role}
Candidate summary: {summary}
Skills they have : {matched}
Skills they lack : {missing}

Generate exactly {num_questions} interview questions now.""")
    ])

    chain = prompt | llm_strict | StrOutputParser()

    raw = chain.invoke({
        "num_questions": num_questions,
        "name":          candidate_name,
        "role":          job_description[:300],
        "summary":       candidate_summary,
        "matched":       ", ".join(matched_skills or []),
        "missing":       ", ".join(missing_skills or [])
    })

    # Parse JSON safely — handle markdown fences if LLM adds them
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            cleaned = parts[1] if len(parts) > 1 else cleaned
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        questions = json.loads(cleaned.strip())
        print(f"  Generated {len(questions)} questions successfully")
        return questions
    except json.JSONDecodeError as e:
        print(f"  Warning: JSON parse failed ({e}), using fallback")
        return _fallback_questions(num_questions)


def _fallback_questions(n: int) -> list:
    """
    Returns generic but solid questions if LLM
    JSON parsing fails. Ensures the interview
    can always proceed regardless of LLM issues.
    """
    base = [
        {
            "id": 1,
            "question": (
                "Describe your most technically complex data project. "
                "What was your specific role, what tools did you use, "
                "and what was the measurable outcome?"
            ),
            "competency": "Technical depth and impact",
            "type": "technical"
        },
        {
            "id": 2,
            "question": (
                "Tell me about a time you had to explain a complex "
                "data finding to a non-technical business stakeholder. "
                "How did you approach it and what was the result?"
            ),
            "competency": "Communication and stakeholder management",
            "type": "behavioural"
        },
        {
            "id": 3,
            "question": (
                "Imagine you join this team and discover the existing "
                "data pipeline has significant quality issues affecting "
                "business decisions. What steps would you take in your "
                "first 30 days to address this?"
            ),
            "competency": "Problem solving and initiative",
            "type": "situational"
        },
        {
            "id": 4,
            "question": (
                "What specifically attracts you to this role and "
                "organisation? How does it align with where you want "
                "to be in your career in the next 3 years?"
            ),
            "competency": "Role fit and motivation",
            "type": "role-fit"
        },
        {
            "id": 5,
            "question": (
                "Walk me through how you stay current with new "
                "developments in data and analytics. Give a specific "
                "example of something you learned recently and applied "
                "in your work."
            ),
            "competency": "Learning agility and curiosity",
            "type": "behavioural"
        }
    ]
    return base[:n]


# ── Answer Scoring ────────────────────────────────────────

def score_answer(
    question: dict,
    answer: str,
    job_description: str,
    candidate_summary: str
) -> dict:
    """
    Scores a single interview answer on a 1-10 scale.

    Evaluates answer against:
    - Relevance to the specific question asked
    - Use of concrete examples and specifics
    - Depth of knowledge demonstrated
    - Clarity and structure of the response

    Returns dict with score, feedback, strengths,
    and areas for improvement.
    """
    # Handle empty or very short answers immediately
    if not answer or len(answer.strip()) < 15:
        return {
            "score":        0,
            "feedback":     "No substantive answer was provided.",
            "strengths":    "N/A",
            "improvements": "A detailed answer is required."
        }

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a senior HR interviewer scoring
a candidate's answer to an interview question.

Be fair, specific, and constructive in your assessment.

Scoring guide:
9-10 : Exceptional — specific, well-structured, concrete example,
       directly relevant, demonstrates deep expertise
7-8  : Strong — clear and relevant with good depth,
       solid example, mostly well-structured
5-6  : Adequate — answers the question but lacks depth
       or specificity, example is vague
3-4  : Weak — partially addresses the question,
       very vague, no real example given
1-2  : Poor — off-topic, incomplete, or demonstrates
       significant lack of relevant knowledge

Return ONLY valid JSON with exactly these four keys:
{{
  "score": <integer between 1 and 10>,
  "feedback": "<2-3 sentence overall assessment>",
  "strengths": "<one sentence on what was strong>",
  "improvements": "<one sentence on what would improve this answer>"
}}
No extra text. No markdown. Pure JSON only."""),
        ("human", """Question asked  : {question}
Competency tested: {competency}
Role context    : {role}
Candidate background: {summary}

Candidate answer:
{answer}

Score this answer now.""")
    ])

    chain = prompt | llm_strict | StrOutputParser()

    raw = chain.invoke({
        "question":   question["question"],
        "competency": question.get("competency", "General"),
        "role":       job_description[:200],
        "summary":    candidate_summary[:300],
        "answer":     answer[:1500]
    })

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            cleaned = parts[1] if len(parts) > 1 else cleaned
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        result = json.loads(cleaned.strip())

        # Validate score is in expected range
        score = result.get("score", 5)
        if not isinstance(score, (int, float)):
            score = 5
        result["score"] = max(1, min(10, int(score)))
        return result

    except json.JSONDecodeError:
        return {
            "score":        5,
            "feedback":     "Answer received and noted.",
            "strengths":    "Candidate provided a response.",
            "improvements": "Adding specific examples would strengthen this answer."
        }


# ── Final Interview Report ────────────────────────────────

def generate_interview_report(
    candidate_name: str,
    questions: list,
    answers: list,
    scores: list,
    match_score: float,
    job_description: str
) -> dict:
    """
    Generates the final interview report after all
    questions are answered and scored.

    Combined scoring formula:
    - 40% weight on resume match score
    - 60% weight on interview performance
    This weights live performance more heavily
    than the initial resume screening.

    Decision thresholds:
    >= 70% → STRONG HIRE
    >= 55% → PROCEED TO NEXT ROUND
    >= 40% → HOLD — FURTHER REVIEW NEEDED
    < 40%  → NOT RECOMMENDED

    CRITICAL: The written report text is always
    consistent with the decision badge.
    """
    print("\n[Interview Agent] Generating final report...")

    # Calculate average interview score out of 10
    valid_scores = [
        s.get("score", 0) for s in scores
        if isinstance(s.get("score"), (int, float))
    ]
    avg_interview_score = (
        round(sum(valid_scores) / len(valid_scores), 1)
        if valid_scores else 0
    )

    # Combined score — converts interview avg to percentage
    # interview avg is /10, match_score is /100
    # formula: (match_score * 0.4) + (interview_avg * 10 * 0.6)
    combined_score = round(
        (match_score * 0.4) + (avg_interview_score * 10 * 0.6),
        1
    )

    # Determine decision FIRST — before writing the report
    # so the LLM can write text consistent with the decision
    if combined_score >= 70:
        decision = "STRONG HIRE"
    elif combined_score >= 55:
        decision = "PROCEED TO NEXT ROUND"
    elif combined_score >= 40:
        decision = "HOLD — FURTHER REVIEW NEEDED"
    else:
        decision = "NOT RECOMMENDED"

    print(f"  Avg interview score : {avg_interview_score}/10")
    print(f"  Combined score      : {combined_score}%")
    print(f"  Decision            : {decision}")

    # Build Q&A summary for context
    qa_summary = ""
    for i, (q, a, s) in enumerate(
        zip(questions, answers, scores), 1
    ):
        qa_summary += (
            f"Q{i} ({q.get('type', 'general')}): "
            f"{q['question']}\n"
            f"Answer: {a[:300]}\n"
            f"Score: {s.get('score', 0)}/10 — "
            f"{s.get('feedback', '')}\n\n"
        )

    # CRITICAL: Decision is passed into the prompt
    # so the report text always matches the badge
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a senior HR director writing
a final hiring recommendation report.

CRITICAL RULE: Your written text MUST be consistent
with and supportive of this decision: {decision}

Guidelines by decision type:
- STRONG HIRE: Write enthusiastically. Highlight strengths.
  Mention gaps as development areas, not disqualifiers.
- PROCEED TO NEXT ROUND: Write positively. Acknowledge both
  strengths and areas to probe further in the next round.
- HOLD — FURTHER REVIEW NEEDED: Write neutrally. Explain
  specifically what additional information is needed.
- NOT RECOMMENDED: Write constructively. Explain specific
  gaps clearly. Suggest what would make them a better fit.

Be direct, specific, and professional.
Reference actual question scores and answers.
Maximum 250 words."""),
        ("human", """Candidate       : {name}
Role            : {role}
Resume Match    : {match_score}%
Interview Avg   : {interview_score}/10
Combined Score  : {combined_score}%
Decision        : {decision}

Interview Q&A Summary:
{qa_summary}

Write the final hiring recommendation report now.
Remember: your text must clearly support {decision}.""")
    ])

    chain = prompt | llm | StrOutputParser()

    report = chain.invoke({
        "name":            candidate_name,
        "role":            job_description[:200],
        "match_score":     match_score,
        "interview_score": avg_interview_score,
        "combined_score":  combined_score,
        "decision":        decision,
        "qa_summary":      qa_summary
    })

    return {
        "report":              report.strip(),
        "decision":            decision,
        "avg_interview_score": avg_interview_score,
        "combined_score":      combined_score
    }