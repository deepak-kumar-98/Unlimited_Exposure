import os
import glob
import json
import sys
import csv
import django

# --- DJANGO SETUP BLOCK ---
# 1. Add Project Root to Path (Go up 3 levels from src/setup_pipeline.py)
# Structure: .../unlimited_exposure/project/AI/src/setup_pipeline.py -> ../../../ -> root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# 2. Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "unlimited_exposure.settings")

from django.conf import settings

# 3. Initialize Django if not already done
if not settings.configured:
    django.setup()

from pypdf import PdfReader
from docx import Document
from llm_gateway import UnifiedLLMClient
from vector_store import VectorStore

# Handle typo in filename from previous iterations
try:
    from webscraper import WebScraper
except ImportError:
    from webscrapper import WebScraper

def extract_text_from_file(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    text = ""
    try:
        if ext in ['.txt', '.md']:
            with open(filepath, 'r', encoding='utf-8') as f: text = f.read()
        elif ext == '.pdf':
            reader = PdfReader(filepath)
            for page in reader.pages: 
                page_text = page.extract_text()
                if page_text: text += page_text + "\n"
        elif ext == '.docx':
            doc = Document(filepath)
            for para in doc.paragraphs: text += para.text + "\n"
        elif ext == '.csv':
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    clean = [c.strip() for c in row if c.strip()]
                    if clean: text += ", ".join(clean) + "\n"

        return f"\n--- SOURCE FILE: {os.path.basename(filepath)} ---\n{text}"
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""

def chunk_text(text, chunk_size=2000):
    if not text: return []
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def run_pipeline(): #pass name as an argument
    print("🚀 Starting Backend Setup Pipeline (Multi-Client)...")
    
    # 1. CLIENT ID INPUT
    client_id = input("Enter Client ID (e.g., client_001): ").strip()
    if not client_id:
        print("❌ Client ID is required.")
        return

    try:
        db = VectorStore()
        llm = UnifiedLLMClient()
        scraper = WebScraper()
    except Exception as e:
        print(f"❌ Initialization Failed: {e}")
        return
    
    # Structure: list of (text_chunk, source_id)
    all_chunks_with_meta = []
    
    # 2. FILE INGESTION
    target_folder = input("Enter path to raw documents folder (or press Enter to skip): ").strip()
    if target_folder and os.path.exists(target_folder):
        files = glob.glob(os.path.join(target_folder, "*.*"))
        print(f"📂 Found {len(files)} files.")
        for file in files:
            raw_text = extract_text_from_file(file)
            doc_id = os.path.basename(file)
            if raw_text.strip():
                chunks = chunk_text(raw_text)
                # Attach Doc ID to every chunk
                sourced_chunks = [(c, doc_id) for c in chunks]
                all_chunks_with_meta.extend(sourced_chunks)
                print(f"   - Processed: {doc_id} ({len(chunks)} chunks)")
            else:
                print(f"   - Skipped: {doc_id}")

    # 3. PRIORITY FILE
    priority_file = input("Enter path to a PRIORITY info file (Optional): ").strip()
    if priority_file and os.path.exists(priority_file):
        raw_text = extract_text_from_file(priority_file)
        doc_id = os.path.basename(priority_file)
        if raw_text.strip():
            chunks = chunk_text(raw_text)
            sourced_chunks = [(c, doc_id) for c in chunks]
            all_chunks_with_meta.extend(sourced_chunks)
            print(f"   - ⭐ Processed Priority File: {doc_id}")

    # 4. WEB SCRAPING
    scrape_input = input("Enter website URL to scrape (or press Enter to skip): ").strip()
    if scrape_input:
        web_text = scraper.scrape_page(scrape_input)
        if web_text:
            web_chunks = chunk_text(web_text)
            # Use URL as document ID
            sourced_chunks = [(c, scrape_input) for c in web_chunks]
            all_chunks_with_meta.extend(sourced_chunks)
            print(f"   - Processed website: {scrape_input}")

    # 5. SAVE TO DB (Updated Signature)
    if all_chunks_with_meta:
        print(f"\n💾 Saving {len(all_chunks_with_meta)} chunks for client '{client_id}'...")
        # Note: Now passing list of tuples
        db.add_documents(client_id, all_chunks_with_meta)
        print("✅ Data stored in Vector DB.")
    else:
        print("⚠️ No content found. Skipping DB save.")

    # 6. GENERATE FAQ
    print("\n🧠 Reading Client Knowledge Base...")
    full_knowledge = db.get_all_text(client_id)
    
    if not full_knowledge:
        print("❌ Database empty for this client.")
        return

    context_slice = full_knowledge[:450000]

    print("🧠 Generating FAQ.json via LLM...")
    
    system_prompt = """
    You are an expert customer support architect.
    Generate a robust FAQ database in strict JSON format.
    Format: {"faqs": [{"questions": ["..."], "answer": "..."}]}
    """
    
    response = llm.generate_text(
        system_prompt, 
        f"Content Source:\n{context_slice}",
        temperature=0.1,
        json_mode=True
    )
    
    if not response:
        print("❌ Failed to generate text from LLM.")
        return

    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        json_output = json.loads(clean_json)
        
        if isinstance(json_output, dict) and "faqs" in json_output:
            faq_data = json_output["faqs"]
        elif isinstance(json_output, list):
            faq_data = json_output
        else:
            faq_data = list(json_output.values())[0] if json_output else []

        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', client_id)
        os.makedirs(data_dir, exist_ok=True)
        output_path = os.path.join(data_dir, "faq.json")
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(faq_data, f, indent=4)
        print(f"✅ FAQ saved to: {output_path}")
        
    except Exception as e:
        print(f"❌ Error creating FAQ JSON: {e}")

if __name__ == "__main__":
    run_pipeline()