import sys
import os
import django
import google.generativeai as genai
from openai import OpenAI
from anthropic import Anthropic

# 1. Add Project Root to Path (Go up 3 levels from src/file.py to root)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# 2. Point to your Django Settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "unlimited_exposure.settings")

# 3. Import Settings (Django will auto-load now)
from django.conf import settings

# 4. Boot Django
if not settings.configured:
    django.setup()

# #-----------------------------------


# from openai import OpenAI
# from anthropic import Anthropic
# # from config import settings
# from django.conf import settings

class UnifiedLLMClient:
    def __init__(self):
        self.provider = settings.API_PROVIDER
        self.chat_model = settings.CHAT_MODEL
        self.embedding_model = settings.EMBEDDING_MODEL
        self.api_key = settings.API_KEY
        self.base_url = getattr(settings, 'BASE_URL', None) # Handle optional base_url

        if self.provider == "claude":
            self.client = Anthropic(api_key=self.api_key)
        
        elif self.provider == "gemini":
            # Configure the global Gemini instance
            genai.configure(api_key=self.api_key)
            self.client = genai # Store the module reference or specific client if needed
         
        else:
            # Mistral, DeepSeek, and OpenAI use the OpenAI SDK
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def get_embedding(self, text: str):
        """Generates vector embeddings for semantic search."""
        text = text.replace("\n", " ")
        
        if self.provider == "claude":
             raise NotImplementedError("Claude SDK does not support embeddings directly. Use OpenAI, Mistral, or Gemini.")

        elif self.provider == "gemini":
            # Gemini Embedding Implementation
            # Note: Ensure settings.EMBEDDING_MODEL is valid (e.g., 'models/text-embedding-004')
            result = genai.embed_content(
                model=self.embedding_model,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']

        else:
            # OpenAI / Compatible SDKs
            return self.client.embeddings.create(input=[text], model=self.embedding_model).data[0].embedding

    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.5, json_mode: bool = False):
        try:
            if self.provider == "claude":
                response = self.client.messages.create(
                    model=self.chat_model,
                    max_tokens=1024,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                return response.content[0].text
            
            # --- GEMINI ---
            elif self.provider == "gemini":
                # Create the model instance with system instruction
                model = genai.GenerativeModel(
                    model_name=self.chat_model,
                    system_instruction=system_prompt
                )
                
                # Configure generation parameters
                generation_config = genai.types.GenerationConfig(
                    temperature=temperature,
                    response_mime_type="application/json" if json_mode else "text/plain"
                )

                response = model.generate_content(
                    user_prompt,
                    generation_config=generation_config
                )
                return response.text

            # --- OPENAI / COMPATIBLE ---
            else:
                params = {
                    "model": self.chat_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": temperature,
                }
                if json_mode and self.provider == "openai":
                    params["response_format"] = {"type": "json_object"}

                response = self.client.chat.completions.create(**params)
                return response.choices[0].message.content

        except Exception as e:
            print(f"❌ API Error ({self.provider}): {e}")
            return None
        

#-------------------------------------
# HOW TO SWITCH BETWEEN API PROVIDERS
#-------------------------------------

"""One small thing to remember:
While the code in llm_engine_api.py doesn't change, you must update your settings.py (or environment variables) to switch providers:

Set API_PROVIDER = "gemini"

Set CHAT_MODEL to a valid Gemini model (e.g., "gemini-1.5-flash").

Set EMBEDDING_MODEL (e.g., "models/text-embedding-004", "text-embedding-3-small") if you are using the vector store features."""