import json
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_retries=1
)

def analyze_jd_node(state: dict) -> dict:
    """
    Agent 2 — JD Analyzer
    
    Reads the job description from state,
    extracts required skills, preferred skills,
    and seniority level.
    """
    print("\n[Agent 2] JD Analyzer running...")

    prompt = ChatPromptTemplate.from_messages([
        ("system", """Analyze this job description.
Return ONLY a valid JSON object with exactly these keys:
{{
  "required_skills": ["skill1", "skill2"],
  "preferred_skills": ["skill1", "skill2"],
  "seniority_level": "junior or mid or senior"
}}
No extra text. No markdown. Pure JSON only."""),
        ("human", "{job_description}")
    ])

    chain = prompt | llm | StrOutputParser()
    raw_output = chain.invoke({
        "job_description": state["job_description"]
    })

    try:
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        data = json.loads(cleaned.strip())
    except json.JSONDecodeError:
        print(f"  Warning: JSON parse failed, using defaults")
        data = {
            "required_skills": [],
            "preferred_skills": [],
            "seniority_level": "mid"
        }

    print(f"  Required skills : {data.get('required_skills')}")
    print(f"  Seniority level : {data.get('seniority_level')}")

    return {
        "required_skills":  data.get("required_skills", []),
        "preferred_skills": data.get("preferred_skills", []),
        "seniority_level":  data.get("seniority_level", "mid")
    }