import os
import sys
import csv
from typing import List, Dict, Optional
import hashlib  # <--- 1. NEW IMPORT

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

from pypdf import PdfReader
from docx import Document
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

SYSTEM_PROMPT_CACHE = {} # <--- 2. NEW GLOBAL VARIABLE

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


# ==========================================
# 3. PROMPT GENERATION (Consolidated)
# ==========================================

def generate_dynamic_system_prompt(
    client_id: str, 
    personas: List[str] = None
) -> str:
    """
    Creates a custom System Prompt using a unified logic flow.
    
    Logic:
    1. If 'personas' are provided -> Generate prompt by blending these personas.
    2. If 'personas' list is empty -> Auto-discover content from DB:
       - Looks for any document IDs that are URLs (regex match).
       - Extracts first 2000 chars of that content.
       - Generates a prompt based on that content.
    3. If neither provided/found -> Return a default helpful assistant prompt.
    """
    
    # --- STRATEGY 1: EXPLICIT PERSONAS ---
    if personas:
        normalized_personas = sorted([p.strip().lower() for p in personas if p.strip()])
        
        if normalized_personas:
            cache_key = f"{client_id}_persona_{hashlib.md5(''.join(normalized_personas).encode()).hexdigest()}"
            
            if cache_key in SYSTEM_PROMPT_CACHE:
                print(f"⚡ Returning cached System Prompt for personas: {normalized_personas}")
                return SYSTEM_PROMPT_CACHE[cache_key]

            print(f"🧠 Generating System Prompt from Personas: {normalized_personas}...")
            instruction = f"""
            Create a highly effective System Prompt for an AI Chatbot.
            The chatbot must embody the following personas: {', '.join(personas)}.
            
            Instructions:
            1. Blend these personas seamlessly.
            2. Define the tone, style, and behavior guidelines.
            3. Output ONLY the System Prompt text. Do not include markdown quotes.
            """
            
            generated_prompt = llm_client.generate_text(
                system_prompt="You are an expert Prompt Engineer.",
                user_prompt=instruction,
                temperature=0.7
            )
            
            if generated_prompt:
                SYSTEM_PROMPT_CACHE[cache_key] = generated_prompt
                return generated_prompt

    # --- STRATEGY 2: AUTO-DISCOVER DB CONTENT (URL Fallback) ---
    print(f"ℹ️ No personas provided. Checking DB for URL-based content for client: {client_id}")
    
    # Fetch content from DB where doc_id looks like a URL (limit 2000 chars)
    db_content = vector_db.get_url_content_for_client(client_id, max_chars=2000)

    if db_content:
        cache_key = f"{client_id}_auto_url_content_{hashlib.md5(db_content.encode()).hexdigest()}"
        if cache_key in SYSTEM_PROMPT_CACHE:
            print(f"⚡ Returning cached System Prompt from auto-discovered content.")
            return SYSTEM_PROMPT_CACHE[cache_key]

        print(f"🧠 Generating System Prompt from DB URL content...")
        instruction = """
        Analyze the provided content snippet (extracted from the client's website).
        Create a professional, robust 'System Prompt' (System Instruction) for an AI Chatbot that will represent this entity.
        The System Prompt should define the bot's persona, tone, limitations, and core mission based on the text provided.
        Output ONLY the System Prompt text. Do not include markdown quotes.
        """
        
        generated_prompt = llm_client.generate_text(
            system_prompt="You are an expert AI Architect.",
            user_prompt=f"{instruction}\n\nCONTENT PREVIEW:\n{db_content}",
            temperature=0.5
        )
        
        if generated_prompt:
            SYSTEM_PROMPT_CACHE[cache_key] = generated_prompt
            return generated_prompt

    # --- STRATEGY 3: DEFAULT ---
    print("ℹ️ No personas or URL content found. Using default prompt.")
    return "You are a helpful, professional AI assistant. Answer user queries politely and accurately using the provided context."


def generate_rag_response(
    client_id: str, 
    user_query: str, 
    system_prompt: Optional[str] = None, 
    chat_history: List[Dict[str, str]] = None
) -> str:
    
    # 1. Retrieve
    retrieved_docs = vector_db.search(client_id, user_query, limit=10)
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