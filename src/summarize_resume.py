import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 1. Load environment variables
load_dotenv()

def summarize_resume(file_path):
    # 2. Load the PDF
    # This splits the PDF into pages and extracts the text
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    
    # 3. Initialize the LLM (Groq)
    llm = ChatGroq(
        temperature=0, 
        model_name="llama-3.3-70b-versatile" # Or whichever model you used in test_setup.py
    )
    
    # 4. Create a Prompt Template
    # We don't just send raw text; we give the LLM "instructions" (System) 
    # and "data" (Human)
    template = """
    You are an expert HR Talent Intelligence Assistant. 
    Summarize the following resume text into 3 sections:
    1. Key Technical Skills
    2. Professional Experience Highlights
    3. Education & Certifications
    
    Resume Content:
    {resume_content}
    """
    prompt = ChatPromptTemplate.from_template(template)
    
    # 5. The Chain (LCEL)
    # This is the "Input -> Process -> Output" pipeline
    chain = prompt | llm | StrOutputParser()
    
    # 6. Run the chain
    # We take the text from all pages and join them together
    full_text = " ".join([doc.page_content for doc in docs])
    response = chain.invoke({"resume_content": full_text})
    
    return response

if __name__ == "__main__":
    # Ensure you have a file named sample_resume.pdf in your data folder!
    resume_path = "data/sample_resume.pdf"
    
    if os.path.exists(resume_path):
        print(f"--- Summarizing: {resume_path} ---")
        summary = summarize_resume(resume_path)
        print(summary)
    else:
        print(f"Error: {resume_path} not found. Please add a PDF to the data folder.")