#-----------------------------------------------
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
#---------------------------------------

import psycopg2
from psycopg2.extras import execute_values
# from config import settings
from src.llm_gateway import UnifiedLLMClient


class VectorStore:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            dbname=settings.POSTGRES_DB_NAME,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD
        )
        self.client = UnifiedLLMClient()
        self._init_db()

    def _init_db(self):
        """Enable pgvector extension and create table with client isolation."""
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    client_id TEXT,
                    content TEXT,
                    embedding vector(1536) 
                );
            """)
            # Migration: Ensure client_id column exists
            cur.execute("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='client_id') THEN 
                        ALTER TABLE documents ADD COLUMN client_id TEXT; 
                        CREATE INDEX idx_client_id ON documents(client_id);
                    END IF; 
                END $$;
            """)
        self.conn.commit()

    def add_documents(self, client_id: str, texts: list[str]):
        """Generate embeddings and save to DB for a specific client."""
        if not texts: return
        
        data = []
        print(f"⚙️ Generating embeddings for {len(texts)} chunks...")
        for text in texts:
            vector = self.client.get_embedding(text)
            data.append((client_id, text, vector))

        with self.conn.cursor() as cur:
            execute_values(cur, 
                "INSERT INTO documents (client_id, content, embedding) VALUES %s", 
                data
            )
        self.conn.commit()
        print(f"✅ Added {len(texts)} documents for Client: {client_id}")

    def search(self, client_id: str, query: str, limit: int = 3):
        """Semantic search filtered by client_id."""
        query_vector = self.client.get_embedding(query)
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT content, 1 - (embedding <=> %s::vector) as similarity
                FROM documents
                WHERE client_id = %s
                ORDER BY similarity DESC
                LIMIT %s;
            """, (query_vector, client_id, limit))
            results = cur.fetchall()
            
        return [row[0] for row in results]

    def get_all_text(self, client_id: str):
        """Fetch all text for a specific client (for FAQ generation)."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT content FROM documents WHERE client_id = %s;", (client_id,))
            return " ".join([row[0] for row in cur.fetchall()])