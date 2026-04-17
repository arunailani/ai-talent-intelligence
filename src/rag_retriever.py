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
    model_name="sentence-transformers/all-mpnet-base-v2"
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
            metadata = match.get("metadata") or {}
            results.append({
                "summary":    metadata.get("summary", ""),
                "source":     metadata.get("source", ""),
                "similarity": round(match["similarity"] * 100, 1)
            })

        return results

    except Exception:
        # Fail silently — RAG context is enhancement,
        # not a hard requirement for the pipeline to run
        return []