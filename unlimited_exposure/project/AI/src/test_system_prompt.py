import sys
import os

# --- DJANGO SETUP BLOCK ---
try:
    from django.conf import settings
    # Access a variable to verify settings are actually configured
    _ = settings.BASE_DIR 
except Exception:
    # Fix: Go up 3 levels to find the Django root (src -> AI -> project -> root)
    # This ensures we can find the 'unlimited_exposure' package
    django_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
    if django_root not in sys.path:
        sys.path.insert(0, django_root)
    
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "unlimited_exposure.settings")
    
    import django
    django.setup()
    from django.conf import settings

# --- 1. SETUP ENVIRONMENT ---
# Add parent directory (project/AI) to path so we can import modules as 'from src...'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# We rely on api_services to handle the Django setup internally
from src.api_services import generate_dynamic_system_prompt
from src.vector_store import VectorStore

def main():
    print("🧪 Starting System Prompt Generation Test...\n")
    
    CLIENT_ID = "test_prompt_client_999"
    
    # --- TEST CASE 1: PERSONA BASED ---
    print("--- [Test 1] Generating from Personas ---")
    personas = ["Experienced Salesman", "Friendly Customer Support", "Slightly Witty"]
    print(f"INPUT Personas: {personas}")
    
    prompt_1 = generate_dynamic_system_prompt(
        client_id=CLIENT_ID, 
        personas=personas
    )
    
    print("\n🤖 GENERATED PROMPT (Personas):")
    print("-" * 40)
    print(prompt_1)
    print("-" * 40)
    print("\n")

    # --- TEST CASE 2: DB AUTO-DISCOVERY ---
    print("--- [Test 2] Generating from DB Content (Auto-Discovery) ---")
    
    # 1. Inject dummy data to simulate a scraped website
    # We bypass the scraper and talk to VectorDB directly for this test
    print("⚙️ Injecting dummy URL content into Vector DB...")
    vector_db = VectorStore()
    dummy_text = """
    Welcome to TechNova Solutions. We provide cloud infrastructure for startups.
    Our pricing starts at $20/month. We value transparency, speed, and innovation.
    Our support team is available 24/7.
    """
    dummy_url = "https://technova-dummy-site.com"
    
    # Add document manually: list of (text, document_id)
    vector_db.add_documents(CLIENT_ID, [(dummy_text, dummy_url)])
    
    # 2. Call generation WITHOUT personas (should trigger DB fallback)
    print("INPUT: No personas provided (Triggering DB lookup)...")
    prompt_2 = generate_dynamic_system_prompt(
        client_id=CLIENT_ID, 
        personas=[]
    )
    
    print("\n🤖 GENERATED PROMPT (DB Content):")
    print("-" * 40)
    print(prompt_2)
    print("-" * 40)

if __name__ == "__main__":
    main()