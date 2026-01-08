import os
import sys
import csv
from typing import List, Dict, Optional

# --- DJANGO SETUP BLOCK ---
try:
    from django.conf import settings
    _ = settings.BASE_DIR 
except Exception:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "unlimited_exposure.settings")
    import django
    django.setup()
    from django.conf import settings

from .pypdf import PdfReader
from .docx import Document
from .llm_gateway import UnifiedLLMClient
from .vector_store import VectorStore

try:
    from .webscraper import WebScraper
except ImportError:
    try:
        from .webscrapper import WebScraper
    except ImportError:
        pass

vector_db = VectorStore()
llm_client = UnifiedLLMClient()

def extract_text_from_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return ""

    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8') as f: text = f.read()
        elif ext == '.pdf':
            print(f"📄 Extracting PDF: {file_path}-----------------------")
            reader = PdfReader(file_path)
            for page in reader.pages:
                t = page.extract_text()
                if t: text += t + "\n"
        elif ext == '.docx':
            doc = Document(file_path)
            for para in doc.paragraphs: text += para.text + "\n"
        elif ext == '.csv':
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    clean = [c.strip() for c in row if c.strip()]
                    if clean: text += ", ".join(clean) + "\n"
        
        # We keep the header in the text content for LLM context, 
        # but we also pass the filename separately as document_id
        return f"\n--- SOURCE: {os.path.basename(file_path)} ---\n{text}"
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return ""

def chunk_text_content(text: str, chunk_size: int = 2000) -> List[str]:
    if not text: return []
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def scrape_website_content(url: str) -> str:
    try:
        scraper = WebScraper()
        return scraper.scrape_page(url)
    except Exception as e:
        print(f"Scraping failed: {e}")
        return ""

def ingest_data_to_vector_db(client_id: str, content_source: str, is_url: bool = False) -> Dict[str, int]:
    text_content = ""
    document_id = ""

    if is_url:
        print(f"🕷️ Scraping URL: {content_source}")
        text_content = scrape_website_content(content_source)
        document_id = content_source # Use URL as ID
    else:
        print(f"📂 Reading File: {content_source}")
        text_content = extract_text_from_file(content_source)
        document_id = os.path.basename(content_source) # Use Filename as ID

    if not text_content.strip():
        return {"status": "failed", "chunks": 0}

    chunks = chunk_text_content(text_content)
    
    if chunks:
        # Create list of (text, doc_id) tuples
        docs_with_metadata = [(chunk, document_id) for chunk in chunks]
        vector_db.add_documents(client_id, docs_with_metadata)
        return {"status": "success", "chunks": len(chunks)}
    
    return {"status": "empty", "chunks": 0}

def generate_rag_response(
    client_id: str, 
    user_query: str, 
    system_prompt: Optional[str] = None, 
    chat_history: List[Dict[str, str]] = None
) -> str:
    
    # 1. Retrieve
    retrieved_docs = vector_db.search(client_id, user_query, limit=5)
    if not retrieved_docs:
        return "I apologize, but I don't have enough information."

    context_text = "\n\n".join(retrieved_docs)[:30000]

    # 2. History
    history_context = ""
    if chat_history:
        recent_msgs = chat_history[-4:]
        history_lines = [f"{m.get('role','').capitalize()}: {m.get('content','')}" for m in recent_msgs]
        history_context = "\n".join(history_lines)

    # 3. Prompt
    if not system_prompt:
        system_prompt = "You are a helpful assistant. Answer using Context and History only."

    full_user_prompt = f"""
Conversation History:
{history_context}

Context Information:
{context_text}

User Question: {user_query}
"""

    return llm_client.generate_text(system_prompt, full_user_prompt, temperature=0.3)