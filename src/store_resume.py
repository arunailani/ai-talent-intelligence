import fitz  # pymupdf
from dotenv import load_dotenv
import os
from supabase import create_client
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# ── Connections ───────────────────────────────────────────
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

embedder = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_retries=1
)

# ── PDF Extraction using pymupdf ──────────────────────────
def extract_text(pdf_path: str) -> str:
    """
    Extracts clean text from any PDF — including Canva,
    Word exports, and standard PDFs.
    """
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()

    # Basic cleanup — remove excessive blank lines
    lines = [line.strip() for line in full_text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned

# ── LLM Summary using LCEL chain ─────────────────────────
def summarize_resume(raw_text: str) -> str:
    """
    Sends resume text to Groq/Llama and returns
    a clean plain-English summary. Uses LCEL pipe syntax.
    LCEL means: prompt | llm | parser — each step feeds
    its output into the next step automatically.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert HR analyst.
Read the resume below and return a concise 3-sentence summary covering:
1. Candidate name and current role
2. Key technical skills
3. Most relevant experience

Return plain text only. No bullet points. No JSON."""),
        ("human", "{resume_text}")
    ])

    chain = prompt | llm | StrOutputParser()
    summary = chain.invoke({"resume_text": raw_text[:4000]})
    return summary.strip()

# ── Store in Supabase ─────────────────────────────────────
def store_resume(pdf_path: str):
    """
    Full pipeline:
    PDF → extract text → summarize → embed → store in Supabase
    """
    print(f"\nProcessing: {pdf_path}")
    print("Step 1/3 — Extracting text with pymupdf...")
    raw_text = extract_text(pdf_path)
    print(f"           Extracted {len(raw_text)} characters")

    print("Step 2/3 — Summarizing with Groq/Llama...")
    summary = summarize_resume(raw_text)
    print(f"           Summary: {summary[:120]}...")

    print("Step 3/3 — Generating embedding and storing...")
    # Embed the summary — more focused than embedding raw text
    # Embed summary + raw content preview for richer semantic signal
    embed_text = f"{summary}\n\n{raw_text[:1000]}"
    embedding_vector = embedder.embed_query(embed_text)

    # Build the record matching your Supabase table schema
    record = {
        "content": raw_text,
        "metadata": {
            "source": pdf_path,
            "summary": summary,
            "char_count": len(raw_text)
        },
        "embedding": embedding_vector
    }

    response = supabase.table("resumes").insert(record).execute()

    if response.data:
        print(f"\nStored successfully — Row ID: {response.data[0]['id']}")
        print(f"Summary saved: {summary}")
    else:
        print(f"\nError storing: {response}")

# ── Run ───────────────────────────────────────────────────
if __name__ == "__main__":
    store_resume("data/sample_resume.pdf")