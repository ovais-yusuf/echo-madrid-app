# Echo Madrid refresh and deployment

## Verified configuration versus unknown production state

The supplied local directory was a source export without `.git`. Its README names
Railway, while `render.yaml` describes Render plus an external Neon database.
A fresh GitHub checkout subsequently confirmed `main` as the default branch and
`a86d83f` as its starting commit (a Render free-tier deployment fix). The original
application sources matched the export, and changes were transferred into a clean
checkout preserving that history. This supports Render as the intended backend
configuration, but deployed settings still need verification. Railway CLI found no
linked project and could not refresh its session because network access failed.
Do not create a second production database.

## Build and schema

The API image now builds from the **repository root** using `api/Dockerfile`.
It includes `api/` and `pipeline/`, with `PYTHONPATH=/app/api:/app`.
Secrets and local environment files are excluded from the image context.

Run migrations once before releasing the new API/worker:

```sh
cd api
alembic upgrade head
```

Railway's root `railway.toml` declares the API build, startup script and health
check. The startup script applies migrations before starting the API. Ensure the existing Railway API service's root directory is `/`, config is
`railway.toml`, and Dockerfile is `api/Dockerfile`. The existing Next.js service
continues to build from `/web`; do not apply the backend Railway config to it.
Render's existing blueprint now uses the root context and migrates before starting
the API. No paid service is created by this change.

## Choose one hosted scheduler

**GitHub Actions (included):** `.github/workflows/ingestion.yml` runs at minutes
7, 17, 27, 37, 47 and 57. Configure repository Actions secrets:

- `INGEST_DATABASE_URL`: direct/session-pooled PostgreSQL connection to the **same
  database and schema used by the API**. For Neon use the direct endpoint.
- `FOOTBALL_DATA_API_KEY`: existing provider token.

Apply the migration first, enable Actions, then run **Refresh football data** with
`workflow_dispatch`. Scheduled workflows run on GitHub's default branch only;
verify that its code matches the deployment branch. GitHub schedules can be delayed,
may have account usage limits, and may be disabled after inactivity on public repos.
This is hosted execution: the MacBook is not required. No OpenAI key is needed.

**Existing Railway/Render worker capacity:** deploy the same root-context API image
with start command `python -m pipeline.worker`, the same `DATABASE_URL`, and provider
key. Set `INGEST_INTERVAL_SECONDS=600` (minimum 300). On Railway use a separate
worker config with no HTTP health check and override the API start command; do not
inherit `healthcheckPath=/health` for a worker. On Render use a background worker or
cron job (`python -m pipeline.worker --once`). Creating worker/cron capacity can incur
charges: no service or subscription was purchased. Disable the GitHub schedule if
using a continuous worker to avoid redundant cycles.

The worker's session-level PostgreSQL advisory lock spans all resource jobs and
replicas, including CLI imports. **Transaction poolers are not supported** for the
worker; use a direct URL or session pooler. An interrupted process releases its lock
on disconnect. The next owner marks interrupted runs failed. Each resource writes
in one transaction, preserving the last successful values on failure.

## Runtime variables

| Service | Variable | Purpose |
| --- | --- | --- |
| API | `DATABASE_URL` | PostgreSQL database with migrations applied |
| API | `OPENAI_API_KEY` | Server-only Ask Echo query selection |
| Worker | `DATABASE_URL` | Same database, direct/session-pooled URL |
| Worker | `FOOTBALL_DATA_API_KEY` | Existing provider subscription |
| Worker | `INGEST_INTERVAL_SECONDS` | 600 default, 300 minimum |
| Next.js | `API_BASE_URL` | API URL, server-only |
| Next.js | `LEGACY_SITE_URL` | Public FastAPI Ask Echo URL |

No provider/OpenAI keys belong in `NEXT_PUBLIC_*` variables. Existing `api/.env`
loading is preserved for local development. From repo root use `PYTHONPATH=api:.`.

## Data behavior and operational checks

Each cycle refreshes Madrid's current matches, La Liga and Champions League tables,
La Liga's full match schedule, and the next opponent's own matches. Up to three
unresolved older Madrid fixtures are rechecked individually so prior-season games
can recover after season rollover. The provider's external IDs preserve identity
through postponements and rescheduling. No matches are deleted when absent from a
response. Authoritative table rows replace the current table within a transaction.
Empty/malformed resources fail without advancing their successful timestamp.

One client limits requests to 8/minute (below the free-plan 10/minute allowance),
with 30-second HTTP timeouts, four attempts, backoff/jitter, and `Retry-After` handling
for 429 and transient server errors. Long retry delays abandon the job rather than
violating the provider's requested wait. Authentication and coverage errors are not
retried. Other resources still run after one resource fails. Do not run unrelated
apps against the same token without allocating request headroom.

`GET /freshness` reports matches, PD standings and CL standings independently.
30 minutes without a successful import is stale. An import time records observation,
not a promise that the provider has already published the latest score. Unknown
legacy import times stay unknown. Browser snapshots refresh every minute while
visible and never trigger upstream ingestion. Refresh buttons only reload stored data.

Logs include entity, status, count and safe error type/HTTP status (never provider response bodies). Ingestion logs older than 30
days are pruned except the latest attempt and success for each resource. Historical
standings snapshots are kept only when the actual provider table changes; none are
backfilled. Old matches are preserved. Monitor log/table growth in production.

After deployment, verify all of the following; a push alone is not verification:

1. `/health` returns 200 and database migration is `c9e20261111`.
2. A hosted worker/Actions run succeeds with match and standings records.
3. `/freshness` timestamps advance across two separate scheduled cycles.
4. `/matchday`, `/matches?view=results&season=all`, and `/standings?competition=PD`
   agree with provider responses for the same competition/season.
5. Repeat for CL; a provider 403 or missing table must show an unavailable state.
6. Check Home, Matchday, Team and both tables on mobile and desktop.

## Provider limits and feature boundaries

Checked against https://www.football-data.org/pricing on 2026-11-10:
the free plan has 12 competitions, 10 calls/minute, league tables, and **delayed
scores and schedules**. It is not a real-time score feed. Paid livescores and deeper
statistics are separate subscriptions; none have been changed. Do not promise a
fixed delay duration because the pricing page does not specify one.

Opponent samples use the opponent's own imported schedule and report sample size,
period and freshness. Missing/uncovered history is explicit. Match recaps only use
stored teams, score and status; lineups, player events, possession and tactics are
unavailable. Shared PNG cards include source and import time. Calendar UIDs are
stable by provider match ID; downloaded files are not an auto-updating subscription.

CL total tables retain provider stage/group labels and are displayed separately;
knockout stages are not turned into a league. Unsupported multi-stage duplicate
team rows fail safely. Table-change explanations are observed deltas plus results
in the snapshot interval, not invented causal explanations. The hypothetical La Liga
simulator adds one imaginary match and sorts by points, overall GD, goals scored and
previous position. It does not implement head-to-head or all official tie-break rules.

Ask Echo accepts up to 12 prior conversation turns for follow-up intent, but retrieves
fresh evidence for every answer. Calculations and final factual wording are
server-generated; old assistant answers are never accepted as database facts.

## Tests

```sh
PYTHONPATH=api:. python -m pytest api/tests -q
cd web
npm ci
npm test
npm run typecheck
npm run build
```

CI includes a disposable PostgreSQL 16 service to test actual migrations and
cross-connection advisory locking. That test skips locally without
`TEST_POSTGRES_URL`. Never point that variable at a development/production database.


## Startup command troubleshooting

If a deployment builds successfully but exits with status 127 and reports the whole
`cd ... && alembic ... && uvicorn ...` expression as "not found", the hosting
command override has interpreted nested shell quoting incorrectly. The API now
uses `api/start.sh` for migrations and server startup. Both the image default and
the Blueprint call the same script without nested quotes.

For an existing Render service, sync its Blueprint. If its Docker Command setting
still contains the old inline command, set it to `sh /app/api/start.sh` (without
quotes), or clear the override to use the image default, and redeploy the latest
commit. This requires no paid pre-deploy hook. The script stops if migrations fail,
uses the provided `PORT` (8000 by default), and replaces the shell with Uvicorn for
normal signal handling. Worker start commands remain `python -m pipeline.worker`.
