import json
import os
import pickle
import numpy as np
from src.llm_gateway import UnifiedLLMClient
from config import settings

class MatcherAPI:
    def __init__(self):
        self.client = UnifiedLLMClient()
        # Dictionary to hold data for multiple clients
        # Structure: { 'client_id': { 'data': [...], 'embeddings': [...] } }
        self.client_cache = {} 

    def _get_paths(self, client_id):
        """Returns paths for faq.json and embeddings.pkl based on client_id"""
        base_dir = os.path.join("data", client_id)
        return {
            "faq": os.path.join(base_dir, "faq.json"),
            "cache": os.path.join(base_dir, "faq_embeddings.pkl")
        }

    def _load_client_data(self, client_id):
        """
        Loads FAQ and Embeddings for a specific client into memory.
        """
        # If already loaded, skip
        if client_id in self.client_cache:
            return True

        paths = self._get_paths(client_id)
        
        # 1. Load FAQ JSON
        if not os.path.exists(paths["faq"]):
            print(f"⚠️ FAQ file not found for client: {client_id} at {paths['faq']}")
            return False
            
        try:
            with open(paths["faq"], 'r', encoding='utf-8') as f:
                faq_data = json.load(f)
        except Exception as e:
            print(f"❌ Error loading FAQ for {client_id}: {e}")
            return False

        # 2. Load or Compute Embeddings
        embeddings = []
        cache_valid = False
        
        if os.path.exists(paths["cache"]):
            faq_mtime = os.path.getmtime(paths["faq"])
            cache_mtime = os.path.getmtime(paths["cache"])
            if cache_mtime > faq_mtime:
                try:
                    with open(paths["cache"], 'rb') as f:
                        embeddings = pickle.load(f)
                    if len(embeddings) == len(faq_data):
                        cache_valid = True
                except:
                    pass

        if not cache_valid:
            print(f"⚙️ Computing embeddings for client: {client_id}")
            embeddings = []
            for item in faq_data:
                anchor = item['questions'][0]
                vector = self.client.get_embedding(anchor)
                embeddings.append(vector)
            
            # Save cache
            try:
                with open(paths["cache"], 'wb') as f:
                    pickle.dump(embeddings, f)
            except Exception as e:
                print(f"⚠️ Could not save cache for {client_id}: {e}")

        # 3. Store in Memory
        self.client_cache[client_id] = {
            "data": faq_data,
            "embeddings": embeddings
        }
        return True

    def _cosine_similarity(self, v1, v2):
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    def find_best_match(self, user_query: str, client_id: str):
        """
        Finds best match for a specific client.
        """
        # Ensure client data is loaded
        if not self._load_client_data(client_id):
            return None, 0.0

        client_ctx = self.client_cache[client_id]
        faq_data = client_ctx["data"]
        embeddings = client_ctx["embeddings"]

        if not faq_data:
            return None, 0.0

        query_vector = self.client.get_embedding(user_query)
        best_score = -1
        best_idx = -1

        for i, faq_vector in enumerate(embeddings):
            score = self._cosine_similarity(query_vector, faq_vector)
            if score > best_score:
                best_score = score
                best_idx = i

        if best_score >= settings.FAQ_SIMILARITY_THRESHOLD:
            return faq_data[best_idx], best_score
        
        return None, best_score