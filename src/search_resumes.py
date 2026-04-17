from dotenv import load_dotenv
import os
from supabase import create_client
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

# ── Connections ───────────────────────────────────────────
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY")
)

# Must match store_resume.py — same model, same 768 dimensions
embedder = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-mpnet-base-v2"
)

# ── Search Function ───────────────────────────────────────
def search_candidates(query: str, top_k: int = 3):
    """
    Converts a plain English query into a vector,
    then finds the most semantically similar resumes
    stored in Supabase using cosine similarity.
    """
    print(f"\nSearching for: '{query}'")
    print("Generating query embedding...")

    # Same embedding model converts query to 768-dim vector
    query_vector = embedder.embed_query(query)

    # Supabase RPC calls our match_resumes SQL function
    response = supabase.rpc(
        "match_resumes",
        {
            "query_embedding": query_vector,
            "match_count": top_k
        }
    ).execute()

    if not response.data:
        print("No results found.")
        return

    print(f"\nTop {len(response.data)} result(s):")
    print("-" * 55)

    for i, match in enumerate(response.data, 1):
        metadata   = match.get("metadata") or {}
        summary    = metadata.get("summary", "No summary available")
        source     = metadata.get("source", "Unknown")
        score      = round(match["similarity"] * 100, 1)

        print(f"Result {i}")
        print(f"  Source      : {source}")
        print(f"  Match score : {score}%")
        print(f"  Summary     : {summary}")
        print("-" * 55)

# ── Run ───────────────────────────────────────────────────
if __name__ == "__main__":
    search_candidates("data analyst with Python and ESG experience")
    search_candidates("team leader with vendor management skills")