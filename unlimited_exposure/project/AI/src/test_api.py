import os
import sys
import time

# --- DJANGO SETUP (CRITICAL FIX) ---
# We need to initialize Django because config.py uses django.conf.settings.
# 1. Add project root to path so we can find the 'unlimited_exposure' module.
#    Structure: root/project/AI/src/test_api_services.py -> ../../.. -> root
django_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if django_project_root not in sys.path:
    sys.path.insert(0, django_project_root)

# 2. Set the settings module (matches your settings.py location)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "unlimited_exposure.settings")

# 3. Setup Django
import django
django.setup()

# --- PATH FIX ---
# Ensure we can import config and src modules (relative to project/AI)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api_services import (
    extract_text_from_file,
    chunk_text_content,
    ingest_data_to_vector_db,
    generate_rag_response
)

def create_dummy_file(filename="test_knowledge.txt"):
    """Creates a temporary file with some dummy data for testing."""
    content = """
    RustCheck Test Service Information
    ----------------------------------
    1. The 'SuperShield' protection plan costs $129.99 per year.
    2. We are open from 9 AM to 5 PM, Monday through Friday.
    3. Our headquarters is located in Toronto, Canada.
    4. To book an appointment, call 1-800-RUST-OFF.
    """
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return os.path.abspath(filename)

def main():
    print("🧪 Starting API Services Test...")
    
    # 1. Test Variables
    CLIENT_ID = "test_api_client_001"
    TEST_FILE = "test_knowledge.txt"
    
    # 2. Setup Dummy Data
    print(f"\n[1/4] Creating dummy file: {TEST_FILE}")
    file_path = create_dummy_file(TEST_FILE)
    
    try:
        # 3. Test Extraction & Chunking (Indirectly via Ingest)
        print(f"\n[2/4] Testing Ingestion for client '{CLIENT_ID}'...")
        result = ingest_data_to_vector_db(
            client_id=CLIENT_ID,
            content_source=file_path,
            is_url=False
        )
        print(f"   ✅ Ingestion Result: {result}")
        
        if result['status'] != 'success':
            print("   ❌ Ingestion failed. Stopping test.")
            return

        # 4. Test RAG Generation
        print(f"\n[3/4] Testing RAG Generation...")
        query = "How much does the SuperShield plan cost?"
        print(f"   ❓ Query: {query}")
        
        # We pass a simple history just to test that logic too
        mock_history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]
        
        response = generate_rag_response(
            client_id=CLIENT_ID,
            user_query=query,
            chat_history=mock_history
        )
        
        print(f"\n   🤖 Response:\n   {response}")
        
        if "129.99" in response:
            print("\n   ✅ SUCCESS: The model retrieved the correct price from the ingested file.")
        else:
            print("\n   ⚠️ WARNING: The model response might be hallucinated or generic. Check DB connection.")

    except Exception as e:
        print(f"\n❌ Test Failed with Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 5. Cleanup
        print(f"\n[4/4] Cleaning up {TEST_FILE}...")
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)
        print("Done.")

if __name__ == "__main__":
    main()