import fitz  # this is pymupdf — fitz is its internal name

def extract_text_pymupdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    full_text = ""
    
    for page in doc:
        full_text += page.get_text()
    
    doc.close()
    return full_text

if __name__ == "__main__":
    text = extract_text_pymupdf("data/sample_resume.pdf")
    print(text[:1000])