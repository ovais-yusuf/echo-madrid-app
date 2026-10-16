# Echo Madrid: Matches and white theme

This release adds Matches after your Standings review. Verify locally, deploy, and confirm it is live before starting Home or Team.

## Apply to your existing Standings checkout

The ZIP includes the full clean source under `Echo Madrid/`, an incremental `Matches.patch`, and this guide as `START_HERE.md`.

The patch targets the previously delivered Standings release, not the original single-page project. Keep your `.git` directory, `.env` files, and local database. Preserve any local work before applying:

```bash
# From your existing repository root:
git status --short
git apply --check /path/to/Matches.patch
git apply /path/to/Matches.patch
```

If the check fails, compare the affected paths with the clean source folder instead of forcing the patch. Do not delete your existing checkout or overwrite local configuration. The archive contains no secrets, environment files, installed dependencies, git metadata, database contents, or build output. Environment examples are included.

## Run locally

Use your existing populated local PostgreSQL database and `api/.env`. No new migrations, keys, dependencies, or environment variables are required for this update.

Terminal 1, from the repository root:

```bash
docker compose up -d
cd api
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Terminal 2, from the repository root:

```bash
cd web
npm ci
npm run dev
```

Keep the existing `web/.env.local`:

```dotenv
API_BASE_URL=http://localhost:8000
LEGACY_SITE_URL=http://localhost:8000
```

For a fresh web checkout, create it with `cp .env.example .env.local`. The web frontend needs Node.js 20.9 or newer; Node.js 22 is suitable. If you are setting up Python from scratch, create `.venv` in `api` and copy `.env.example` to `.env` only if no existing config is present.

Open **http://localhost:3000/matches**. Standings remains at **http://localhost:3000/standings**. `/` still redirects to Standings until Home is built.

If match data is missing, run the existing idempotent pipeline from the repository root with the Python environment active and your football-data.org key configured:

```bash
python -m pipeline.ingest_matches
```

Neither page refresh nor changing filters triggers ingestion or an OpenAI request. The browser gets server-rendered data from Next.js; Next.js fetches FastAPI on the server with no cache and a 10-second timeout. No CORS change or frontend database credentials are needed.

## What changed

- White cards and a soft white page background, navy text, and restrained gold highlights across Standings and Matches. The existing FastAPI Ask Echo HTML uses the same light palette. Its URL, form behavior, and grounding code are preserved.
- The shared navigation enables Matches and highlights the current page. Home and Team remain upcoming items.
- `GET /matches` provides a Madrid-only paginated snapshot with competition and season metadata. All SQL remains in `api/app/queries.py`. The new endpoint reuses `get_team_matches`, also used by the original REST routes and Ask Echo.
- The page has Upcoming, Results, and All matches views, competition and season filters, pagination, refresh, UTC times, club crests with fallback initials, and clear empty/error/loading states.
- Results show scores only when stored. Win/draw/loss badges are derived from the stored score from Madrid's perspective. A missing completed score stays unavailable; it is never displayed as 0:0.

## Endpoint and filtering rules

Examples:

```text
GET /matches
GET /matches?view=results
GET /matches?view=upcoming&competition=PD
GET /matches?view=all&season=all&limit=12&offset=12
GET /matches?view=results&season=2026%2F2027
```

Parameters:

- `view`: `upcoming` (default), `results`, or `all`.
- `competition`: optional stored competition code, such as `PD` or `CL`.
- `season`: optional stored season label, exactly as returned in `seasons`. Omit to use the newest season with Madrid matches. `all` includes all stored seasons.
- `limit`: 1 to 100, default 20. The frontend uses 12.
- `offset`: nonnegative, default 0.

The response includes `team`, `matches`, `competitions`, `seasons`, `selected_season`, `imported_at`, `total`, `limit`, `offset`, and `has_more`.

Upcoming includes only `SCHEDULED` and `TIMED` rows whose stored UTC date has not passed, sorted nearest first. Results includes only `FINISHED` rows, sorted newest first. All matches includes every stored status, sorted newest date first. Other clubs' matches never enter the result, even if their local ID happens to be `2`.

The newest stored season is the default across competitions, based on season start date. You can select all seasons or an older label explicitly. Filter choices are derived from Madrid's stored matches.

`imported_at` is the latest successful football-data.org match ingestion completion time, excluding failed runs and standings imports. If it is unavailable, the page says so. It is not a live score timestamp or a guarantee that the source data is current.

Scheduled rows without a confirmed kick-off show the date and "Kick-off not confirmed". Other dates/times display in UTC. Postponed, cancelled, in-play, paused, and stale scheduled rows remain visible under All matches. In-play scores are explicitly labelled as stored data.

## Local browser checks

1. Open Matches through the navigation. Check that only Matches is highlighted; return to Standings and check that its active state switches back.
2. Check the white theme on both pages and the Ask Echo link destination. The fan disclaimer must still be visible.
3. Compare the page with `http://localhost:8000/matches?view=results&limit=12`. Check home/away teams, scores, dates, competition, season, and badges.
4. Switch to Upcoming. Fixtures should be nearest first and have no fabricated score. Compare `view=upcoming` on the API. An empty list is legitimate when no future fixtures have been imported.
5. Apply a competition filter, change season, and try All stored seasons. Apply resets pagination. Reset restores the default season and all competitions for the current view.
6. If there are more than 12 matching rows, test Next and Previous. Counts and filters should remain consistent. An out-of-range page has an explicit empty state and a link back to browsing.
7. Test phone width and keyboard navigation. Filters should fit, cards should stack, and club names should not force horizontal page scrolling. Standings keeps its horizontally scrollable table.
8. Stop FastAPI, reload Matches, and check the recoverable error. Restart it and use Try again. With an empty database, check the separate no-data state instead of sample fixtures.
9. Ask Echo should still work through its existing FastAPI page. This release adds no OpenAI tools or AI-generated match content.

## Validation

From `api` with the Python environment active:

```bash
pytest tests -q
```

From `web`:

```bash
npm run typecheck
npm run build
```

The backend checks use in-memory SQLite and a mocked OpenAI client. They never connect to production, call OpenAI, or consume API requests. PostgreSQL with psycopg v3 remains the application's database setup. Original Alembic migrations are unchanged.

This update passed 23 backend checks. Browser behavior and your populated PostgreSQL database still need your local verification. No production access was used.

## Deploy only after local verification

Keep the same two application services: FastAPI rooted at `api` and Next.js rooted at `web`, alongside the private managed PostgreSQL service. Both application services need this update because Matches adds a new API endpoint, and the legacy Ask Echo HTML palette changes in the API service.

The web service continues to use its Dockerfile and these variables:

- `API_BASE_URL`: the FastAPI private HTTP origin including its actual listening port, or the existing public HTTPS origin if you are using that for verification.
- `LEGACY_SITE_URL`: the browser-accessible public HTTPS origin of the FastAPI app.

The web service receives no database URL or API keys. Keep public database access off.

Review the diff before pushing to `main`, since Railway auto-deploys configured services from that branch. This package has not been pushed or deployed. Verify `/matches` and `/standings` after deployment, then confirm Matches is live before proceeding to Home.
