from dotenv import load_dotenv
import os
from langchain_groq import ChatGroq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("ERROR: GROQ_API_KEY not found in .env file")
    print("Check your .env file has: GROQ_API_KEY=your-key-here")
else:
    print(f"API key loaded: {api_key[:15]}...")
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_retries=1
    )
    
    response = llm.invoke("Say exactly this: Phase 1 setup is working perfectly.")
    
    print("\n--- Response ---")
    print(response.content)
    print("--- Setup Complete ---")