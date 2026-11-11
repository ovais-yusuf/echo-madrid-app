# Echo Madrid

A football data platform with a natural-language query interface. Ask questions
about Real Madrid in plain English and get answers grounded in real data — never
hallucinated.

**Live demo:** https://echo-madrid-production.up.railway.app

## What it does

"Ask Echo" lets you ask questions like *"Where is Real Madrid in the La Liga
table?"* or *"What was their last result?"* and returns answers computed from a
stored database of matches and standings. The language model never invents
statistics — it can only answer from data returned by real database queries, and
says so when the data isn't there.

## Architecture

Echo Madrid is a four-layer system, not a chatbot:

1. **Ingestion pipeline** (`/pipeline`) — scheduled, idempotent jobs that pull
   match and standings data from the football-data.org API and upsert it into
   Postgres. Re-running never creates duplicates (upserts keyed on external IDs
   and composite keys), and every run is logged to an `ingestion_run` table.
2. **Database** — a normalized PostgreSQL schema (teams, matches, standings,
   seasons, competitions), evolved through versioned Alembic migrations.
3. **API** (`/api`) — a typed FastAPI service exposing the data. All query logic
   lives in a shared data-access layer reused by both the REST endpoints and the
   AI layer.
4. **Ask Echo** — a grounded natural-language interface built on OpenAI tool
   calling. The model translates a question into a call against the same query
   functions the API uses, the app executes the real query, and deterministic templates
   render the answer from the returned rows only.

### Grounding design

The core design principle: the LLM is a translator, not a knowledge source. It
selects which query function to call and with what arguments; the application
executes the query and renders factual text from those rows.
Factual responses are rendered deterministically from tool evidence — every
number traces to a database row, and missing data yields "I don't have that"
rather than an invention.

## Stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL
- **AI:** OpenAI API (function/tool calling)
- **Infra:** Docker, Docker Compose, Railway and Render configuration (active host must be verified)
- **Data source:** football-data.org API

## Running locally

```bash
# Start Postgres
docker compose up -d

# Set up the API
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, OPENAI_API_KEY, FOOTBALL_DATA_API_KEY
alembic upgrade head

# Ingest data
cd ..
PYTHONPATH=api:. python -m pipeline.ingest_matches
PYTHONPATH=api:. python -m pipeline.ingest_standings

# Run the app
cd api
uvicorn app.main:app --reload
# open http://localhost:8000
```

## Notes

Echo Madrid is a solo-built engineering project. It is an unofficial fan project
and is not affiliated with Real Madrid CF.
## Application pages

The Next.js frontend in `/web` includes Home, Matches, Matchday, Standings and Team.
Home and Team already exist; this update extends them. Matchday adds provider states,
opponent previews, shareable PNG cards and stable calendar downloads. Standings
switches La Liga/Champions League, records real snapshots and includes an explicitly
hypothetical La Liga simulator. Team includes scoring trends and home/away samples.

All database queries remain in `api/app/queries.py`, shared by REST and Ask Echo.
Ask Echo uses OpenAI for query selection and follow-up intent, then generates factual
answers deterministically with supporting records and independent freshness times.

The repository includes a hosted ingestion worker and GitHub Actions schedule.
**Pushing alone does not configure the database secrets or verify production refresh.**
See [DEPLOYMENT.md](DEPLOYMENT.md) for migration, host configuration, scheduling,
provider limits and production verification. The older LOCAL_REVIEW.md describes the
previous UI patch; DEPLOYMENT.md supersedes its deployment/refresh instructions.
