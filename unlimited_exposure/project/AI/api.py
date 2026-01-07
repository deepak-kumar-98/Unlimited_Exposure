import sys
import os

# --- PATH FIX ---
# This ensures that 'src' can be imported correctly regardless of how uvicorn is started.
# Since api.py is in the root (chatbot/), this adds 'chatbot/' to the python path.
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
# Now Python can find 'src' because the root folder is in sys.path
from src.llm_engine_api import LLMEngineAPI

app = FastAPI(title="Hybrid Restaurant Bot (Multi-Client)")

# CORS Setup - Critical for Frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Engine
# This will load config.py (from root) via the imports in llm_engine_api
try:
    engine = LLMEngineAPI()
    print("✅ LLM Engine Initialized Successfully")
except Exception as e:
    print(f"❌ Engine Initialization Failed: {e}")
    # We don't exit here so the server can at least start and show the error via HTTP if needed
    engine = None

# --- REQUEST MODELS ---
class ChatRequest(BaseModel):
    text: str
    client_id: str
    history: List[Dict[str, str]] = [] # Optional history

class ChatResponse(BaseModel):
    response: str
    similarity_score: Optional[float] = 0.0

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="LLM Engine failed to initialize. Check server logs.")

    if not req.client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    try:
        # Route to the engine with client_id and history
        answer = engine.generate_response(
            user_query=req.text,
            client_id=req.client_id,
            chat_history=req.history
        )
        
        return {
            "response": answer,
            "similarity_score": 0.0 
        }
    except Exception as e:
        print(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health():
    return {"status": "ok", "mode": "multi-client", "root_dir": os.path.abspath(os.path.dirname(__file__))}