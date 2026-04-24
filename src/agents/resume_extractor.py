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

def extract_resume_node(state: dict) -> dict:
    """
    Agent 1 — Resume Extractor
    
    Reads the PDF, extracts text with pymupdf,
    sends to LLM, gets back structured data.
    Updates state with candidate information.
    """
    print("\n[Agent 1] Resume Extractor running...")

    
    import sys
    import os
    sys.path.append(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    from document_extractor import extract_text

    clean_text = extract_text(state["pdf_path"])

    # Ask LLM to extract structured information
    prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert HR analyst and skills taxonomy specialist.
Extract information from this resume carefully.

CRITICAL RULES for skills extraction:

RULE 1 — ALWAYS split compound skill entries into individual skills.
This is the most important rule.

Examples of splitting:
INPUT:  "Big Data - (Hadoop, Spark, Databricks, AWS)"
OUTPUT: ["hadoop", "spark", "databricks", "aws", "big data"]

INPUT:  "Python (Pandas, Numpy, Pyspark)"  
OUTPUT: ["python", "pandas", "numpy", "pyspark"]

INPUT:  "SQL (Oracle, Postgres)"
OUTPUT: ["sql", "oracle", "postgresql"]

INPUT:  "Visualization (Quicksight, Looker Studio, Power BI)"
OUTPUT: ["data visualization", "quicksight", "looker studio", "power bi"]

INPUT:  "Unix, GitHub"
OUTPUT: ["unix", "github"]

RULE 2 — Normalize all skill names to lowercase standard form.
"Power BI" → "power bi"
"AWS" → "aws"  
"PostgreSQL" → "postgresql"

RULE 3 — Infer implicit skills from job titles and responsibilities.
"Project Manager" title → add "project management", "stakeholder management"
"Team Lead" → add "leadership", "team management"
"Vendor Management" mentioned → add "stakeholder management"
"Led a team of 10" → add "people management"

RULE 4 — Include both the category AND individual tools.
"Visualization tools" → include "data visualization" as the category
plus each specific tool separately.

Return ONLY a valid JSON object with exactly these keys:
{{
  "name": "full name as string",
  "email": "email as string or empty string",
  "skills": ["skill1", "skill2", "skill3"],
  "years_experience": 0,
  "summary": "2 sentence summary"
}}

The skills array should have 15-30 individual items for a typical resume.
No extra text. No markdown. Pure JSON only."""),
    ("human", "{resume_text}")
])

    chain = prompt | llm | StrOutputParser()
    raw_output = chain.invoke({"resume_text": clean_text[:4000]})

    # Parse the JSON response safely
    try:
        # Strip markdown code blocks if LLM adds them
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        data = json.loads(cleaned.strip())
    except json.JSONDecodeError:
        print(f"  Warning: JSON parse failed, using defaults")
        data = {
            "name": "Unknown",
            "email": "",
            "skills": [],
            "years_experience": 0,
            "summary": raw_output[:200]
        }

    print(f"  Extracted: {data.get('name')} | "
          f"{len(data.get('skills', []))} skills | "
          f"{data.get('years_experience')} years")

    # Return only the fields this agent is responsible for
    return {
        "candidate_name":  data.get("name", "Unknown"),
        "candidate_email": data.get("email", ""),
        "candidate_skills": data.get("skills", []),
        "years_experience": data.get("years_experience", 0),
        "raw_summary":     data.get("summary", "")
    }