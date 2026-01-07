import os
import sys
import csv
from typing import List, Dict, Optional

#--------------------------
import sys
import os
import django

# 1. Add Project Root to Path (Go up 3 levels from src/file.py to root)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# 2. Point to your Django Settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "unlimited_exposure.settings")

# 3. Import Settings (Django will auto-load now)
from django.conf import settings

# 4. Boot Django
if not settings.configured:
    django.setup()
#---------------------------------

# Add parent directory to path so we can import config and other modules
# In a Django project, he might replace this with standard Django absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from config import settings
from pypdf import PdfReader
from docx import Document
from llm_gateway import UnifiedLLMClient
from vector_store import VectorStore

# Robust import for WebScraper
try:
    from webscraper import WebScraper
except ImportError:
    from webscrapper import WebScraper

# Initialize singletons to reuse connections
# In Django, these might be initialized in apps.py ready() to persist across requests
vector_db = VectorStore()
llm_client = UnifiedLLMClient()

# ==========================================
# 1. HELPER FUNCTIONS (Extract, Chunk, Scrape)
# ==========================================

def extract_text_from_file(file_path: str) -> str:
    """
    Reads a file from disk and returns its text content.
    Supports: .txt, .md, .pdf, .docx, .csv
    """
    if not os.path.exists(file_path):
        # In Django, you might want to log this error using logger.error()
        print(f"File not found: {file_path}")
        return ""

    ext = os.path.splitext(file_path)[1].lower()
    text = ""

    try:
        if ext in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        
        elif ext == '.pdf':
            reader = PdfReader(file_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        elif ext == '.docx':
            doc = Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        
        elif ext == '.csv':
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    # Clean empty cells
                    clean_row = [cell.strip() for cell in row if cell.strip()]
                    if clean_row:
                        text += ", ".join(clean_row) + "\n"
        else:
            print(f"⚠️ Unsupported file extension: {ext}")
            return ""

        return f"\n--- SOURCE: {os.path.basename(file_path)} ---\n{text}"

    except Exception as e:
        print(f"❌ Error reading file {file_path}: {e}")
        return ""


def chunk_text_content(text: str, chunk_size: int = 2000) -> List[str]:
    """
    Splits a long string into a list of smaller strings (chunks)
    for better Vector DB performance.
    """
    if not text:
        return []
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]


def scrape_website_content(url: str) -> str:
    """
    Uses Firecrawl to scrape a website URL and return Markdown text.
    """
    try:
        scraper = WebScraper()
        # This uses the logic defined in src/webscraper.py
        return scraper.scrape_page(url)
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        return ""


# ==========================================
# 2. CORE LOGIC FUNCTIONS (Ingest, Generate)
# ==========================================

def ingest_data_to_vector_db(client_id: str, content_source: str, is_url: bool = False) -> Dict[str, int]:
    """
    Orchestrates the ingestion flow.
    
    Args:
        client_id: The client to associate data with.
        content_source: Either a file path OR a website URL.
        is_url: Set to True if content_source is a URL.
    
    Returns:
        Dict with status and number of chunks saved.
    """
    text_content = ""

    # 1. Extract Text
    if is_url:
        print(f"🕷️ Scraping URL: {content_source}")
        text_content = scrape_website_content(content_source)
    else:
        print(f"📂 Reading File: {content_source}")
        text_content = extract_text_from_file(content_source)

    if not text_content.strip():
        return {"status": "failed", "reason": "No text extracted", "chunks": 0}

    # 2. Chunk Text
    chunks = chunk_text_content(text_content)

    # 3. Save to DB
    if chunks:
        # vector_db handles the embedding generation internally
        vector_db.add_documents(client_id, chunks)
        return {"status": "success", "chunks": len(chunks)}
    
    return {"status": "empty", "chunks": 0}


def generate_rag_response(
    client_id: str, 
    user_query: str, 
    system_prompt: Optional[str] = None, 
    chat_history: List[Dict[str, str]] = None
) -> str:
    """
    Performs the full RAG generation flow.
    
    Args:
        client_id: The client identifier for data isolation.
        user_query: The end user's question.
        system_prompt: Optional custom instruction (e.g., "Answer in Spanish").
                       If None, a default RAG prompt is used.
        chat_history: List of previous messages [{"role": "user", "content": "..."}, ...]
    """
    print(f"🔍 Generating RAG Response for Client: {client_id}")

    # 1. Retrieve Context from Vector DB
    # We fetch top 5 chunks to give the LLM enough information
    retrieved_docs = vector_db.search(client_id, user_query, limit=5)
    
    if not retrieved_docs:
        # You might want to return a specific flag here if you want the frontend to handle empty states
        return "I apologize, but I don't have enough information in my knowledge base to answer that."

    # Join context chunks
    context_text = "\n\n".join(retrieved_docs)
    
    # Safety limit to prevent token overflow (approx 8k tokens)
    context_text = context_text[:30000]

    # 2. Format History (Last 4 turns)
    history_context = ""
    if chat_history:
        recent_msgs = chat_history[-4:]
        history_lines = []
        for msg in recent_msgs:
            role = msg.get('role', 'unknown').capitalize()
            content = msg.get('content', '')
            history_lines.append(f"{role}: {content}")
        history_context = "\n".join(history_lines)

    # 3. Construct System Prompt
    # If the API caller didn't provide a specific system prompt, use the default RAG persona.
    if not system_prompt:
        system_prompt = """
        You are a helpful assistant for a business. 
        Answer the user's question using ONLY the provided Context Information and Conversation History.
        If the answer is not in the context, politely say you don't know.
        """

    # 4. Construct Final User Prompt
    # This combines History + Context + Current Question
    full_user_prompt = f"""
Conversation History:
{history_context}

Context Information:
{context_text}

User Question: {user_query}
"""

    # 5. Call LLM
    # Uses the unified client (OpenAI/Mistral/etc defined in config)
    return llm_client.generate_text(
        system_prompt=system_prompt, 
        user_prompt=full_user_prompt, 
        temperature=0.3
    )