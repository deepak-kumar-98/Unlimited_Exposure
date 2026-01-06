import os
from openai import OpenAI
from anthropic import Anthropic
from config import settings

class UnifiedLLMClient:
    def __init__(self):
        self.provider = settings.API_PROVIDER
        self.chat_model = settings.CHAT_MODEL
        self.embedding_model = settings.EMBEDDING_MODEL
        self.api_key = settings.API_KEY
        self.base_url = settings.BASE_URL

        if self.provider == "claude":
            self.client = Anthropic(api_key=self.api_key)
        else:
            # Mistral, DeepSeek, and OpenAI use the OpenAI SDK
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def get_embedding(self, text: str):
        """Generates vector embeddings for semantic search."""
        if self.provider == "claude":
             # Claude does not currently have a public embedding API in the SDK.
             # You might need to use a separate provider for embeddings if using Claude for Chat.
             raise NotImplementedError("Claude SDK does not support embeddings directly. Use OpenAI or Mistral for this part.")
        
        text = text.replace("\n", " ")
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
            print(f"❌ API Error: {e}")
            return None