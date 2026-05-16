# Dietly Backend

FastAPI API with JWT auth. **PostgreSQL runs in Docker Compose.** Configure secrets via `.env` (copy from `.env.example`).

## Requirements

- Docker & Docker Compose
- LLM provider keys as needed (`LLM_PROVIDER` in `.env`; use `AWS_*` only when `LLM_PROVIDER=bedrock`)

## Configuration

1. Copy `.env.example` → `.env`
2. Set **`JWT_SECRET_KEY`** (long random string, ≥16 characters).
3. Set **`POSTGRES_PASSWORD`** and the matching password inside **`DATABASE_URL`** when connecting from the host.

Compose substitutes **`POSTGRES_PASSWORD`** into the **`db`** service and into the **`app`** container’s `DATABASE_URL` (`...@db:5432/dietly`).  
Your **`DATABASE_URL`** in `.env` should point at **`127.0.0.1:5432`** when you run clients or uvicorn on the host against the published Postgres port.

## Run

**Docker Compose (default)** — app code from the image, uploads in a named volume:

```bash
docker compose up --build -d
```

**With reload** — bind-mounted source and `uvicorn --reload` (same Postgres service):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

- API: http://localhost:8000 (or the host port you set with `APP_PUBLISH_PORT` in `.env`)  
- Docs: http://localhost:8000/docs  

Postgres: service **`db`**, database **`dietly`**, user **`postgres`**. The **`app`** container always gets `DATABASE_URL` pointed at host **`db`** via Compose overrides; keep `DATABASE_URL` in `.env` on **`127.0.0.1`** for host-side tools or local uvicorn against the published DB port.

## Schema

Use **`SCHEMA_AUTO_CREATE=true`** once on an empty database if you are not applying migrations yet; set **`false`** afterward.

On startup, Postgres runs a small idempotent patch so **`users.password_hash`** exists and is NOT NULL.

## Auth

- `POST /api/v1/auth/register` — `{ "email", "password", "full_name?" }`
- `POST /api/v1/auth/login` — `{ "email", "password" }`
- Protected routes: `Authorization: Bearer <access_token>`

Admin routes: `/api/v1/admin/*` (role `admin` in DB).

## API overview

| Prefix | Purpose |
|--------|---------|
| `/api/v1/auth` | Register, login → JWT |
| `/api/v1/users` | Profile, streak, calories, steps goal |
| `/api/v1/admin/stats` | Admin counts |
| `/api/v1/admin/users` | Admin user management |
| `/api/v1/admin/images` | Admin image delete |
| `/api/v1/images` | Meal photos, analysis |
| `/api/v1/meal` | Meal summaries |
| `/api/v1/user-calories` | Activity calories |
| `/api/v1/public` | Rate-limited public analyze |
