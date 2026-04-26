from dotenv import load_dotenv
import os
from supabase import create_client
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

embedder = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

def get_similar_candidates(query: str, top_k: int = 2) -> list:
    """
    Retrieves the top_k most semantically similar
    candidates already stored in Supabase.

    Called by the Report Generator to provide
    comparative context in hiring recommendations.
    Returns empty list gracefully if DB is empty.
    """
    try:
        query_vector = embedder.embed_query(query)

        response = supabase.rpc(
            "match_resumes",
            {
                "query_embedding": query_vector,
                "match_count": top_k
            }
        ).execute()

        if not response.data:
            return []

        results = []
        for match in response.data:
            if match["similarity"] < 0.65:
                continue
            metadata = match.get("metadata") or {}
            summary = metadata.get("summary", "")
            first_sentence = (summary.split(".")[0].strip() + ".") if summary else ""
            results.append({
                "name":       metadata.get("name", metadata.get("source", "Unknown")),
                "skills":     (metadata.get("skills") or [])[:5],
                "similarity": round(match["similarity"] * 100, 1),
                "summary":    first_sentence
            })

        return results

    except Exception:
        # Fail silently — RAG context is enhancement,
        # not a hard requirement for the pipeline to run
        return []