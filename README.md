# Dietly Backend

FastAPI service for meal photos (pluggable vision LLM + S3), meal summaries, activity calories, and a rate-limited public food demo. Clients authenticate with a Firebase **ID token**: `Authorization: Bearer <token>`.

## Prerequisites

- Python 3.12+ (Dockerfile uses 3.13)
- PostgreSQL
- Firebase service account JSON, AWS S3
- One configured **LLM provider** (Gemini, OpenAI, Groq, Ollama, or AWS Bedrock)

## Environment

Create `.env` or `.env.local` in the project root:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/dietly
SCHEMA_AUTO_CREATE=true

FRONTEND_URL=http://localhost:3000

FIREBASE_CREDENTIALS_PATH=/absolute/path/to/serviceAccount.json

# LLM_PROVIDER: gemini | openai | groq | bedrock | ollama
LLM_PROVIDER=gemini

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1

GROQ_API_KEY=
GROQ_MODEL=llama-3.2-11b-vision-preview
GROQ_BASE_URL=https://api.groq.com/openai/v1

# Ollama (OpenAI-compatible /v1; use a vision model, e.g. ollama pull llava)
OLLAMA_BASE_URL=http://127.0.0.1:11434/v1
OLLAMA_MODEL=llava
# OLLAMA_API_KEY=   # optional; set if your Ollama proxy requires Bearer auth

BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-south-1
AWS_S3_BUCKET_NAME=

DEFAULT_AVATAR_URL=
PUBLIC_ANALYZE_DAILY_LIMIT=5
```

Only the variables required for your chosen `LLM_PROVIDER` need to be set (plus shared AWS keys for S3). For Bedrock, the same credentials must allow `bedrock-runtime` inference on the chosen model in that region. For **Ollama**, run a vision-capable model locally (for example `ollama pull llava`) and point `OLLAMA_BASE_URL` at your server’s `/v1` endpoint; `OLLAMA_API_KEY` is optional.

**Note:** After changing `LLM_PROVIDER` or model env vars, restart the app process so the cached provider is rebuilt.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000  
- OpenAPI: http://localhost:8000/docs  

## Docker

Copy `.env.example` to `.env` and set at least Firebase and AWS (or your LLM keys). Compose starts **Postgres 16** (`db`) and the API (`app`); `DATABASE_URL` is set in compose to `...@db:5432/dietly` so the app reaches the DB inside the network. Postgres is exposed on host port **5432** for local tools.

```bash
docker compose up --build
```

- API: http://localhost:8000  
- With `SCHEMA_AUTO_CREATE=true` in `.env`, tables are created on first app startup.

## Database

With `SCHEMA_AUTO_CREATE=true`, the app creates tables from SQLAlchemy models on startup. Use `false` in production if another process owns the schema.

## Auth and roles

1. Sign in with Firebase on the client and send the Firebase **ID token** on each request.
2. New users get `role = user` in the database.
3. Admin APIs are under `/api/v1/admin/` and require `role = admin`. Grant the first admin by updating `users.role` in your database, then use `PATCH /api/v1/admin/users/{id}/role` for further changes. Dashboard counts: `GET /api/v1/admin/stats`. Global image moderation: `GET` / `DELETE /api/v1/admin/images/{image_id}`.

Roles are defined in `app/core/roles.py`. Admin HTTP handlers use `app/controllers/`.

## API overview

| Prefix | Purpose |
|--------|---------|
| `/api/v1/users` | Current user (`/me`, `/me/avatar`, streak, net calories, steps goal) |
| `/api/v1/admin/stats` | Admin: user / image counts |
| `/api/v1/admin/users` | Admin: list (paginated + email filter), get, patch profile, delete, role, user images |
| `/api/v1/admin/images` | Admin: get / delete any image by id |
| `/api/v1/images` | Upload, analyze, list, presigned URLs, `is_meal` |
| `/api/v1/meal` | Meal summaries from images |
| `/api/v1/user-calories` | Activity calories |
| `/api/v1/public` | Unauthenticated food analysis (IP rate limit) |
