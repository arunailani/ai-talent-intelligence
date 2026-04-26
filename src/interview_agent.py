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
    num_questions: int = 9
) -> list:
    """
    Generates exactly 9 purely technical interview questions
    structured as 3 easy → 3 medium → 3 hard, calibrated to
    the candidate's actual background and the role's required skills.

    Returns a list of 9 question dicts, each with:
    id, question text, competency tested, type ("technical"),
    and difficulty ("easy" | "medium" | "hard")
    """
    print(f"\n[Interview Agent] Generating {num_questions} technical questions (3 easy / 3 medium / 3 hard)...")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a senior technical hiring manager who deeply
understands what a high-performing team needs for this specific role.

Generate exactly 9 purely technical interview questions for this candidate.
Structure them in three difficulty tiers — 3 easy, 3 medium, 3 hard.

DIFFICULTY DEFINITIONS:

EASY (questions 1-3) — foundational knowledge, answerable from memory:
  - "What is X and how does it work?"
  - "Explain the difference between X and Y"
  - "What are the key components / steps of X?"

MEDIUM (questions 4-6) — applied knowledge, requires real hands-on experience:
  - "Walk me through how you would implement X"
  - "You have a dataset with problem Y — how do you approach it?"
  - "Describe a time you used X to solve a real problem"

HARD (questions 7-9) — deep expertise, system-level thinking, senior-level:
  - "What are the trade-offs between X and Y at scale?"
  - "How would you debug X when it fails in production?"
  - "Design a system that handles X under these constraints..."

STRICT RULES:
1. ALL 9 questions must be purely technical.
   No behavioural, no situational, no role-fit questions whatsoever.
2. Questions must be specific to the candidate's actual background
   AND the JD's required skills. Reference the actual technologies
   mentioned in both the resume and the job description.
   Do not write generic questions.
3. Difficulty must genuinely progress — easy questions must be easy,
   hard questions must require senior-level depth.
4. Each question should be answerable verbally in 2-4 minutes.
   Not too narrow, not too broad.
5. type must always be "technical" for all 9 questions.

Return ONLY a valid JSON array. No markdown. No extra text.
Exactly this structure for all 9 questions:
[
  {{
    "id": 1,
    "question": "the full question text here",
    "competency": "what specific concept or skill this tests",
    "type": "technical",
    "difficulty": "easy"
  }},
  {{
    "id": 4,
    "question": "the full question text here",
    "competency": "what specific concept or skill this tests",
    "type": "technical",
    "difficulty": "medium"
  }},
  {{
    "id": 7,
    "question": "the full question text here",
    "competency": "what specific concept or skill this tests",
    "type": "technical",
    "difficulty": "hard"
  }}
]

Pure JSON array only. Nothing else."""),
        ("human", """Candidate name   : {name}
Role             : {role}
Candidate summary: {summary}
Skills they have : {matched}
Skills they lack : {missing}

Generate exactly 9 technical questions now:
questions 1-3 easy, 4-6 medium, 7-9 hard.""")
    ])

    chain = prompt | llm_strict | StrOutputParser()

    raw = chain.invoke({
        "num_questions": num_questions,
        "name":          candidate_name,
        "role":          job_description[:400],
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
    Returns 9 purely technical fallback questions (3 easy, 3 medium, 3 hard)
    if LLM JSON parsing fails. Ensures the interview can always proceed.
    """
    base = [
        # ── EASY ─────────────────────────────────────────────
        {
            "id": 1,
            "question": (
                "What is the difference between a primary key and a foreign key "
                "in a relational database? Give an example of each."
            ),
            "competency": "SQL fundamentals",
            "type": "technical",
            "difficulty": "easy"
        },
        {
            "id": 2,
            "question": (
                "What is a pandas DataFrame and how does it differ from a "
                "standard Python list or dictionary? When would you choose one over the other?"
            ),
            "competency": "Python / pandas fundamentals",
            "type": "technical",
            "difficulty": "easy"
        },
        {
            "id": 3,
            "question": (
                "What is a large language model (LLM) and what is the role "
                "of a prompt in interacting with one? Explain in your own words."
            ),
            "competency": "LLM / GenAI fundamentals",
            "type": "technical",
            "difficulty": "easy"
        },
        # ── MEDIUM ───────────────────────────────────────────
        {
            "id": 4,
            "question": (
                "Walk me through how you would write a SQL query to find "
                "the top 5 customers by total revenue in the last 90 days, "
                "including customers with no purchases in that window."
            ),
            "competency": "Applied SQL — aggregation and joins",
            "type": "technical",
            "difficulty": "medium"
        },
        {
            "id": 5,
            "question": (
                "You have a Python script that processes a 10 GB CSV file "
                "and it is running out of memory. Walk me through two or more "
                "concrete approaches you would use to fix this."
            ),
            "competency": "Python performance and memory management",
            "type": "technical",
            "difficulty": "medium"
        },
        {
            "id": 6,
            "question": (
                "Describe how you would build a retrieval-augmented generation "
                "(RAG) pipeline from scratch. What components are required "
                "and what does each one do?"
            ),
            "competency": "RAG architecture and LangChain / vector stores",
            "type": "technical",
            "difficulty": "medium"
        },
        # ── HARD ─────────────────────────────────────────────
        {
            "id": 7,
            "question": (
                "What are the trade-offs between using a vector database "
                "versus a full-text search index (like Elasticsearch) for "
                "semantic search in a production LLM application?"
            ),
            "competency": "Vector search and retrieval systems at scale",
            "type": "technical",
            "difficulty": "hard"
        },
        {
            "id": 8,
            "question": (
                "Your data pipeline runs nightly and produces aggregated "
                "metrics used by the business. One morning the metrics look "
                "wrong but no errors were raised. How do you debug this "
                "systematically and prevent it from recurring?"
            ),
            "competency": "Data quality and pipeline debugging in production",
            "type": "technical",
            "difficulty": "hard"
        },
        {
            "id": 9,
            "question": (
                "Design a system that takes unstructured documents (PDFs, emails, "
                "reports) and allows business users to ask natural-language questions "
                "against them. What are the key components, where are the failure points, "
                "and how would you ensure answer accuracy?"
            ),
            "competency": "End-to-end GenAI system design",
            "type": "technical",
            "difficulty": "hard"
        },
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