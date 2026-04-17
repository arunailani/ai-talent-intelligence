# AI Talent Intelligence Platform

An end-to-end AI-powered recruitment platform built with
LangGraph multi-agent pipeline, semantic resume screening,
and AI-proctored mock interviews.

## What it does

- **Resume Screening** — Upload any PDF resume, paste a job description, and 4 specialised AI agents screen the candidate in under 30 seconds
- **Semantic Skill Matching** — Uses HuggingFace embeddings and cosine similarity to match skills by meaning, not just keywords
- **AI Mock Interview** — Generates targeted questions based on skill gaps, conducts a proctored one-question-at-a-time interview, scores every answer, and produces a final hiring recommendation
- **Automated Workflow** — n8n triggers the full pipeline automatically when a resume is submitted — zero manual steps

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq + Llama 3.3 70B |
| Agent Orchestration | LangGraph StateGraph |
| LLM Framework | LangChain LCEL |
| Embeddings | HuggingFace all-mpnet-base-v2 768-dim |
| Vector Database | Supabase + pgvector |
| Automation | n8n workflows |
| API Layer | FastAPI + Uvicorn |
| UI | Streamlit multipage app |
| Observability | LangSmith tracing |
| Deployment | Render + Streamlit Cloud |

## Architecture

    Resume PDF
        ↓
    pymupdf extraction
        ↓
    LangGraph StateGraph
        ├── Agent 1 — Resume Extractor
        ├── Agent 2 — JD Analyzer
        ├── Agent 3 — Skill Matcher (cosine similarity)
        └── Agent 4 — Report Generator (RAG-enhanced)
        ↓
    Interview Session (Supabase UUID link)
        ↓
    Candidate Interview (proctored, one question at a time)
        ↓
    Per-answer scoring + Final combined report

## Key Engineering Decisions

- **pymupdf over PyPDFLoader** — handles Canva-format PDFs that standard loaders cannot parse
- **Embedding-based skill matching** — cosine similarity at threshold 0.50 correctly handles synonyms and compound skills where exact string matching fails
- **Atomic skill extraction** — Agent 1 splits compound skills like Python (Pandas, Numpy) into individual entries so each skill has its own dense vector
- **Decision-first report generation** — recommendation calculated before LLM prompt so report text is always consistent with the badge
- **RAG-enhanced reports** — Agent 4 retrieves similar past candidates from vector store for comparative context

## Local Setup

Clone the repository:

    git clone https://github.com/arunailani/ai-talent-intelligence
    cd ai-talent-intelligence

Create virtual environment:

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

Add your API keys:

    cp .env.example .env

Open .env and fill in your keys.

Run the UI:

    streamlit run app.py

Run the API:

    uvicorn api:app --reload --port 8000

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| / | GET | Health check |
| /screen | POST | Screen a resume PDF |
| /create-interview | POST | Generate interview link |
| /sessions | GET | Get all interview sessions |
| /sessions/{id} | GET | Get single session |

## Environment Variables

| Variable | Description |
|---|---|
| GROQ_API_KEY | Groq API key for Llama 3.3 70B |
| SUPABASE_URL | Your Supabase project URL |
| SUPABASE_ANON_KEY | Your Supabase anon key |
| LANGCHAIN_API_KEY | LangSmith API key for tracing |
| LANGCHAIN_PROJECT | LangSmith project name |

## Live Demo

- UI: https://yourname-ai-talent.streamlit.app
- API Docs: https://your-api.onrender.com/docs

## Author

Arun Ailani

[LinkedIn](https://linkedin.com/in/arunailani) | [GitHub](https://github.com/arunailani)