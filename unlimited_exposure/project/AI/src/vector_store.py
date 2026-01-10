import sys
import os
import django
import psycopg2
from psycopg2.extras import execute_values

# --- DJANGO SETUP BLOCK ---
# 1. Add Project Root to Path (Go up 3 levels from src/vector_store.py)
# Structure: .../unlimited_exposure/project/AI/src/vector_store.py -> ../../../ -> root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# 2. Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "unlimited_exposure.settings")

from django.conf import settings

# 3. Initialize Django if not already done
if not settings.configured:
    django.setup()

# --- IMPORTS ---
# Use relative import if inside package, or absolute fallback
try:
    from .llm_gateway import UnifiedLLMClient
except ImportError:
    from llm_gateway import UnifiedLLMClient

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
        """Enable pgvector extension and create table with client and document isolation."""
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    client_id TEXT,
                    document_id TEXT,
                    content TEXT,
                    embedding vector(1536) 
                );
            """)
            # Migration: Ensure client_id and document_id columns exist
            cur.execute("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='client_id') THEN 
                        ALTER TABLE documents ADD COLUMN client_id TEXT; 
                        CREATE INDEX idx_client_id ON documents(client_id);
                    END IF;
                    
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='document_id') THEN 
                        ALTER TABLE documents ADD COLUMN document_id TEXT; 
                        CREATE INDEX idx_document_id ON documents(document_id);
                    END IF;
                END $$;
            """)
        self.conn.commit()

    def add_documents(self, client_id: str, docs_with_metadata: list):
        """
        Generate embeddings and save to DB for a specific client.
        
        Args:
            client_id: The client identifier.
            docs_with_metadata: A list of tuples: [(text_chunk, source_document_id), ...]
        """
        if not docs_with_metadata: return
        
        data = []
        # Separate texts for batch embedding (optional optimization, here we do loop for simplicity/safety)
        print(f"⚙️ Generating embeddings for {len(docs_with_metadata)} chunks...")
        
        for text, doc_id in docs_with_metadata:
            # We explicitly strip header lines if needed, but keeping them in 'content' is usually good for context.
            vector = self.client.get_embedding(text)
            data.append((client_id, doc_id, text, vector))

        with self.conn.cursor() as cur:
            execute_values(cur, 
                "INSERT INTO documents (client_id, document_id, content, embedding) VALUES %s", 
                data
            )
        self.conn.commit()
        print(f"✅ Added {len(docs_with_metadata)} documents for Client: {client_id}")

    def search(self, client_id: str, query: str, limit: int = 3):
        """Semantic search filtered by client_id."""
        query_vector = self.client.get_embedding(query)
        
        with self.conn.cursor() as cur:
            # Return content AND document_id if needed (currently just returning content)
            cur.execute("""
                SELECT content, document_id, 1 - (embedding <=> %s::vector) as similarity
                FROM documents
                WHERE client_id = %s
                ORDER BY similarity DESC
                LIMIT %s;
            """, (query_vector, client_id, limit))
            results = cur.fetchall()
            
        # Just return text for RAG context, but you could return (text, doc_id) if your engine needs citations
        return [row[0] for row in results]

    def get_all_text(self, client_id: str):
        """Fetch all text for a specific client (for FAQ generation)."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT content FROM documents WHERE client_id = %s;", (client_id,))
            return " ".join([row[0] for row in cur.fetchall()])
        
    def get_document_text(self, client_id: str, document_id: str) -> str:
        """Fetch all text chunks associated with a specific document_id."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT content FROM documents WHERE client_id = %s AND document_id = %s ORDER BY id ASC;", 
                (client_id, document_id)
            )
            rows = cur.fetchall()
            return "\n".join([row[0] for row in rows]) if rows else ""

    def get_url_content_for_client(self, client_id: str, max_chars: int = 2000) -> str:
        """
        Auto-discovers content from documents that act as URLs (start with http/https).
        Used for fallback system prompt generation.
        """
        with self.conn.cursor() as cur:
            # Postgres regex (~*) looks for document_id starting with http or https (case insensitive)
            cur.execute("""
                SELECT content 
                FROM documents 
                WHERE client_id = %s AND document_id ~* '^https?://'
                ORDER BY id ASC
                LIMIT 50;
            """, (client_id,))
            rows = cur.fetchall()
            
            if not rows:
                return ""
            
            combined = "\n".join([row[0] for row in rows])
            return combined[:max_chars]