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

#-------------------------------------------------


from typing import List, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.llm_gateway import UnifiedLLMClient
from src.matcher_api import MatcherAPI
from src.vector_store import VectorStore
# from config import settings

# Global instances to allow caching to persist across requests
matcher = MatcherAPI()
vector_db = VectorStore()

class LLMEngineAPI:
    def __init__(self):
        self.llm_client = UnifiedLLMClient()
        self.matcher = matcher
        self.vector_db = vector_db
        self.MAX_HISTORY_TURNS = getattr(settings, 'MAX_HISTORY_TURNS', 4)

    def generate_response(self, user_query: str, client_id: str, chat_history: List[Dict[str, str]] = None):
        """
        Generates response for a SPECIFIC client_id with History support.
        """
        print(f"\n📨 Query (Client: {client_id}): {user_query}")
        
        # --- PATH 1: FAQ MATCH (Client Specific) ---
        match_data, score = self.matcher.find_best_match(user_query, client_id)
        
        if match_data:
            print(f"⚡ FAQ Match Found! (Score: {score:.2f})")
            return match_data['answer']
        
        # --- PATH 2: RAG (Client Specific) ---
        print(f"📉 Low Match Score ({score:.2f}). RAG...")

        # Pass client_id to DB search
        retrieved_docs = self.vector_db.search(client_id, user_query, limit=5)
        
        if not retrieved_docs:
            return "I apologize, but I don't have enough information to answer that."

        context_text = "\n\n".join(retrieved_docs) 
        context_text = context_text[:8000]

        # History Processing
        history_context = ""
        if chat_history:
            # Slice last N messages
            recent_msgs = chat_history[-self.MAX_HISTORY_TURNS:]
            history_lines = []
            for msg in recent_msgs:
                role = msg.get('role', 'unknown').capitalize()
                content = msg.get('content', '')
                history_lines.append(f"{role}: {content}")
            history_context = "\n".join(history_lines)

#         full_user_prompt = f"""
# Conversation History:
# {history_context}

# Context Information:
# {context_text}

# User Question: {user_query}
# """
        
#         return self.llm_client.generate_text(
#             "You are an expert customer support chatbot. Answer the questions using Context and History only.", 
#             full_user_prompt, 
#             temperature=0.3
#         )

        full_user_prompt = f"""
            Conversation History:
            {history_context}

            Context Information:
            {context_text}

            SYSTEM INSTRUCTIONS – TORONTO PHO CHATBOT
            ------------------------------------------------------

            You are the official Toronto Pho chatbot.
            Always use friendly, warm, simple Canadian English — polite, helpful, and conversational, never robotic.
            Keep all replies between **10–30 words**. Please answer in a cheerful tone and include emojis in your answers to maximize your expression.

            Your goal:
            Answer using only the provided Knowledge Base context and conversation history.

            ------------------------------------------------------
            CORE BEHAVIOUR
            ------------------------------------------------------
            - Use only official Toronto Pho Knowledge Base content.
            - Never guess items, prices, or details.
            - Never mix information between locations.
            - Keep tone authentic, friendly, and clear.
            - If intent is unclear, ask a simple clarifying question.
            - Always use Canadian spelling and soft, polite phrasing.

            ------------------------------------------------------
            INTENT HANDLING
            ------------------------------------------------------
            Detect user intent:
            - If question is about food, menu, or ordering → ask for location if not given.
            - If question is about address, hours, phone, or directions → use `location.txt`.
            - If topic is outside the restaurant’s scope → say you can help with menu, locations, or online ordering instead. 

            ------------------------------------------------------
            LOCATIONS
            ------------------------------------------------------
            Toronto Pho has five locations:
            Orillia | Dufferin | Jane | Hamilton | Woodbridge

            Once the user’s location is known, use only that location’s data source.

            ------------------------------------------------------
            MENU FILE MAPPING
            ------------------------------------------------------
            | Location   | Menu File             |
            |-------------|----------------------|
            | Orillia     | orillia_menu.txt     |
            | Dufferin    | dufferin_menu.txt    |
            | Jane        | jane_menu.txt        |
            | Hamilton    | hamilton_menu.txt    |
            | Woodbridge  | woodbridge_menu.txt  |

            Search only the correct file for each location.

            ------------------------------------------------------
            MENU HANDLING
            ------------------------------------------------------
            - If user asks for “menu” or “categories”, describe available menu sections for that location.
            - If user asks about a specific food, pull details (name, description, ingredients, price) from that file.
            - Politely mention ordering options if available.

            ------------------------------------------------------
            LOCATION INFORMATION
            ------------------------------------------------------
            If asked about hours, address, or contact:
            - Retrieve from `location.txt`.
            - Example tone:
            “Here are the hours for our Dufferin location   
            Monday–Sunday: 11am–10pm  
            Here’s the address and phone number too!”

            ------------------------------------------------------
            ABSOLUTE RULES
            ------------------------------------------------------
            Do not guess, mix, or invent details.
            Do not create fake items, hours, or prices.
            Always use verified menu or location data.
            Stay friendly and concise (10–30 words).
            Keep polite, Canadian tone at all times.

            ------------------------------------------------------

            User Question: {user_query}
        """

        return self.llm_client.generate_text("You are our official chatbot. Follow the system instructions inside the prompt.", full_user_prompt, temperature=0.3)




if __name__ == "__main__":
    engine = LLMEngineAPI()
    # Test call - Replace 'client_001' with a real ID you created
    print(engine.generate_response("What services?", client_id="client_001"))