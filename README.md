# TFT Recommender

FastAPI app for Teamfight Tactics comp recommendations with a small browser UI.

The app serves a static frontend from FastAPI and exposes JSON endpoints for comp recommendations and TFT questions. For a public portfolio demo, data-loading endpoints are disabled unless an `ADMIN_TOKEN` is configured.

## Tech Stack

- FastAPI
- PostgreSQL with pgvector
- Riot API data ingestion
- Sentence Transformers embeddings
- Google Gemini answer generation
- Vanilla HTML/CSS/JavaScript frontend

## Local Setup

1. Create and fill `.env` from `.env.example`.
2. Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

3. Run the app:

```powershell
py -m uvicorn main:app --host 127.0.0.1 --port 8002 --reload
```

4. Open:

```text
http://127.0.0.1:8002
```

## Public Demo Mode

Leave `ADMIN_TOKEN` unset in production. Then these endpoints stay disabled:

- `POST /api/load/champions`
- `POST /api/load/items`
- `POST /api/load/matches`

The public demo can still use:

- `GET /`
- `GET /api/health`
- `GET /api/config`
- `GET /api/comps`
- `POST /api/ask`

Preload your hosted Postgres database before sharing the demo link.

## Deployment On Render

Use a Web Service with:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Set these environment variables in Render:

```env
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
DB_PORT=5432
RIOT_API_KEY=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
```

Do not set `ADMIN_TOKEN` for the public portfolio demo unless you want admin imports enabled.

## Notes

This app depends on a PostgreSQL database with the `vector` extension enabled. Supabase, Neon, Railway, and Render Postgres can work, as long as pgvector is available.
