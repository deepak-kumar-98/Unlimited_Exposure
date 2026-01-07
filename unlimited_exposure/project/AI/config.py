import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # --- API CONFIG ---
    API_PROVIDER = os.getenv("API_PROVIDER", "openai").lower()
    API_KEY = os.getenv("API_KEY", "")
    BASE_URL = os.getenv("BASE_URL", None) 

    # --- FIRECRAWL CONFIG ---
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
    
    # Models
    # Ensure your chosen provider supports embeddings! 
    # OpenAI: text-embedding-3-small, Mistral: mistral-embed
    CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # --- DATABASE CONFIG (Postgres) ---
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "vectordb")
    DB_USER = os.getenv("POSTGRES_USER", "user")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

    # --- LOGIC THRESHOLDS ---
    # 0.0 to 1.0 (Cosine Similarity). 0.8 is a good starting point.
    FAQ_SIMILARITY_THRESHOLD = 0.8 
    
    # Paths
    FAQ_FILE_PATH = os.path.join("data", "faq.json")

    # --- CONVERSATION MEMORY ---
    # Number of recent turns (User + Assistant pairs) to include in context
    MAX_HISTORY_TURNS = 4

settings = Settings()