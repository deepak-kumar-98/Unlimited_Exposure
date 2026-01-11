# Unlimited Exposure — AI Chatbot Backend

Welcome to the Unlimited Exposure backend — a Django REST API that powers a Retrieval-Augmented Generation (RAG) chatbot with multi-tenant support, document ingestion, and pluggable LLM providers (OpenAI / Anthropic / Mistral).

This README explains the end-to-end flow, how components fit together, how to run the project locally, and how to interact with the API.

---

## Quick Architecture Summary

- `accounts/` — Handles user registration, `Profile` and `Organization` models; every `Profile` belongs to an `Organization`.
- `project/` — Chat, ingestion and RAG logic. Key models: `IngestedContent`, `ChatSession`, `ChatMessage`, `SystemSettings`.
- `project/AI/src/` — LLM and vector pipeline: `llm_gateway.py`, `vector_store.py`, `api_services.py` implement embedding, storage, retrieval and prompt composition.
- Postgres with `pgvector` (see `docker-compose.yml`) stores persistent data; vector index handled in `vector_store`.

Design patterns:
- Tenant isolation: always derive `organization` from `request.user.profile` and scope queries to `profile` or `organization`.
- System prompts: org-scoped prompts with global fallback; active prompts are unique (old active ones are deactivated when new ones are created).

---

## End-to-end Flow (High-level)

1. User signs up and a `Profile` is created and assigned to an `Organization`.
2. User uploads documents (files or URLs) to `/ingest/`. The backend:
	 - Persists an `IngestedContent` record with `ingestion_status="processing"`.
	 - Extracts plain text (PDF, DOCX, CSV, TXT) via `api_services.extract_text_from_file` or scrapes the URL.
	 - Splits text into chunks and stores vectors in the vector store via `vector_store.add_documents(client_id, docs_with_metadata)`.
	 - Updates `chunk_count` and `ingestion_status` on the DB record.
3. User queries the chatbot at `/rag/` with `query` (and optionally `chat_id` to continue a session). The backend:
	 - Resolves the active `SystemSettings` (org -> global fallback).
	 - Retrieves semantically relevant chunks from the vector store (`vector_db.search`).
	 - Builds a prompt combining system prompt, retrieved context, and recent chat history.
	 - Calls the LLM via `llm_gateway.UnifiedLLMClient.generate_text()` and stores assistant response as `ChatMessage`.

---

## Key files to inspect
- `project/models.py` — ingest/chat/system models
- `accounts/models.py` — `Profile`, `Organization`
- `project/views.py` — API endpoints for ingestion, chat, sessions, and system prompts
- `project/AI/src/api_services.py` — ingestion helpers, prompt generation, RAG orchestration
- `project/AI/src/llm_gateway.py` — LLM SDK abstraction
- `project/AI/src/vector_store.py` — vector DB interface
- `unlimited_exposure/settings.py` — environment-controlled configuration

---

## Environment & Configuration

Set environment variables in a `.env` file or your environment. Important variables used in `settings.py` and the AI pipeline:

```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=exposure
POSTGRES_PORT=5432
PGADMIN_DEFAULT_PORT=8080

API_PROVIDER=openai        # or 'claude', 'mistral'
CHAT_MODEL=gpt-4o         # model name used by chat
EMBEDDING_MODEL=text-embedding-3-small
API_KEY=sk-...
BASE_URL=                # optional, for custom base urls
```

The `docker-compose.yml` includes a `postgres` service (pgvector image) and `pgadmin` for local development.

---

## Local Development (quick start)

Install dependencies (recommended in virtualenv):

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Run DB migrations:

```bash
cd unlimited_exposure
python manage.py migrate
```

Start the server:

```bash
python manage.py runserver
```

Bring up Postgres + PgAdmin (optional):

```bash
docker-compose up -d
```

---

## API Endpoints & Examples

Headers:

```
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

1) Ingest files & URLs

POST `/ingest/` — multipart form payload

curl example (file):

```bash
curl -X POST "http://localhost:8000/ingest/" \
	-H "Authorization: Bearer $TOKEN" \
	-F "files=@/path/to/file.pdf"
```

For URLs, POST JSON with `urls` array.

2) Start / continue RAG chat

POST `/rag/`

```bash
curl -X POST "http://localhost:8000/rag/" \
	-H "Authorization: Bearer $TOKEN" \
	-H "Content-Type: application/json" \
	-d '{"query":"What does the user manual say about installation?"}'
```

Include `chat_id` in request body to append to an existing session.

3) Create system prompt

POST `/system-prompt/` with `system_prompt` string in JSON. If you provide `org_id` in query params, the prompt will be scoped to that org; otherwise it becomes a global prompt.

4) List sessions and messages

GET `/sessions/` — lists user's chat sessions
GET `/chats/<chat_id>/` — lists messages for session

---

## Important Implementation Notes / Patterns

- Security: always derive `organization` from `request.user.profile` and scope DB queries to `profile` or `organization` to prevent privilege escalation.
- System prompt selection follows org → global fallback; creating a new prompt marks previous active prompt inactive.
- Ingested content stores `data_url` (path or URL) and `chunk_count`; ingestion returns status and chunk count.
- `project/AI/src/api_services.py` contains helper utilities for text extraction (`pypdf`, `python-docx`), chunking, and RAG orchestration.
- Vector store is keyed by `client_id` (use the profile ID as string) so vector data is isolated per user.

---

## Troubleshooting & FAQ

- `File not found` or empty ingestion:
	- Confirm `default_storage` location and that `MEDIA_ROOT` in `settings.py` is writable.
	- Check logs printed by `api_services.extract_text_from_file`.

- LLM API errors:
	- Confirm `API_KEY`, `API_PROVIDER`, and `BASE_URL` (if using custom endpoints).
	- `llm_gateway` may raise `NotImplementedError` for embeddings under certain providers (e.g., Claude). Use OpenAI-style provider for embeddings.

- Vector search returns nothing:
	- Confirm ingestion succeeded and `chunk_count` > 0 on `IngestedContent` record.
	- Ensure `vector_store.add_documents` executed without errors (check logs).

---

## Contributing / Extending

- Add new LLM providers in `project/AI/src/llm_gateway.py`. Keep the `get_embedding` and `generate_text` signatures stable.
- When adding features that are user/org scoped, follow the DB pattern: `uploaded_by = ForeignKey(Profile)` and `organization = ForeignKey(Organization, null=True, blank=True)`.
- Any feature that exposes or mutates tenant data must validate `profile` and `organization` before acting.

---

If you'd like, I can also:
- Add a `docs/` folder with sequence diagrams and example payloads
- Scaffold Postman / HTTPie examples for every endpoint
- Add a small `devbox` script to set environment variables and run migrations

Enjoy exploring the codebase — open an issue or ask for targeted walkthroughs (vector store, embeddings, or the RAG prompt design) and I will help.
