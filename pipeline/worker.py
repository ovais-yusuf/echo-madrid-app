"""Hosted ingestion. Never imported/started by a visitor request.

One PostgreSQL session advisory lock serializes all provider work across replicas.
Use a direct DB URL or session pooler, not a transaction pooler, for this worker.
"""
import argparse
import logging
import os
import signal
import threading
import httpx
from datetime import timedelta

from sqlalchemy import delete, select, text, or_
from app.config import get_football_data_api_key
from app.database import engine, SessionLocal
from app.models import IngestionRun, Match, Team, utc_now
from pipeline.ingest_matches import FootballDataClient, ingest_matches
from pipeline.ingest_standings import ingest_standings

log = logging.getLogger(__name__)
LOCK_ID = 86002026
stop = threading.Event()


def record_job(client, entity, fetch, ingest):
    with SessionLocal() as db:
        run = IngestionRun(source="football-data.org", entity_type=entity,
                           started_at=utc_now(), status="running", records_upserted=0)
        db.add(run)
        db.commit()
        try:
            payload = fetch()
            count = ingest(db, payload)
            run.status, run.records_upserted = "success", count
            run.finished_at = utc_now()
            db.commit()
            log.info("ingestion entity=%s status=success records=%s", entity, count)
        except Exception as exc:
            db.rollback()
            run.status, run.finished_at = "failed", utc_now()
            # Do not persist provider response bodies, URLs or credentials.
            run.error = f"HTTPStatusError:{exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
            db.commit()
            log.error("ingestion entity=%s status=failed error=%s", entity, run.error)
        db.refresh(run)
        db.expunge(run)
        return run


def match_rows(payload):
    rows = payload.get("matches")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty or invalid match payload; keep prior success timestamp")
    return rows


def run_once(only=None):
    results = []
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Hosted ingestion requires PostgreSQL advisory locks")
    # A dedicated connection holds the session lock across per-resource commits.
    with engine.connect() as lock:
        acquired = lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID})
        lock.commit()
        if not acquired:
            log.info("ingestion skipped: another worker owns the lock")
            return [IngestionRun(status="skipped", records_upserted=0)]
        try:
            with SessionLocal() as db:
                # Once we own the global lock, any old running job was interrupted.
                for run in db.scalars(select(IngestionRun).where(IngestionRun.status == "running")):
                    run.status, run.finished_at, run.error = "failed", utc_now(), "Interrupted"
                # Keep the latest successful and attempted run for every resource,
                # even during a prolonged outage; prune older operational logs.
                keep = set()
                for entity in db.scalars(select(IngestionRun.entity_type).distinct()):
                    for status in (None, "success"):
                        query = select(IngestionRun.id).where(IngestionRun.entity_type == entity)
                        if status:
                            query = query.where(IngestionRun.status == status)
                        ident = db.scalar(query.order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc()).limit(1))
                        if ident:
                            keep.add(ident)
                db.execute(delete(IngestionRun).where(IngestionRun.id.not_in(keep), IngestionRun.started_at < utc_now() - timedelta(days=30)))
                db.commit()
            with FootballDataClient(get_football_data_api_key()) as client:
                if only in (None, "match"):
                    results.append(record_job(client, "match", lambda: client.get_team_matches(86), lambda db, p: ingest_matches(db, match_rows(p))))
                for code in ("PD", "CL"):
                    if only in (None, f"standing:{code}"):
                        results.append(record_job(client, f"standing:{code}", lambda c=code: client.get_competition_standings(c), ingest_standings))
                if only is None:
                    # A full current league schedule supports points explanations and rollover.
                    results.append(record_job(client, "league:PD", lambda: client.get("/competitions/PD/matches"), lambda db, p: ingest_matches(db, match_rows(p))))
                    with SessionLocal() as db:
                        from app.queries import get_real_madrid, get_team_matches
                        madrid = get_real_madrid(db)
                        fixtures = get_team_matches(db, madrid.id, limit=1, statuses=("SCHEDULED", "TIMED"), after=utc_now(), ascending=True) if madrid else []
                        opponent_id = None
                        if fixtures:
                            m = fixtures[0]
                            opponent_id = (m.away_team if m.home_team_id == madrid.id else m.home_team).external_id
                    if opponent_id:
                        # This is the opponent's OWN schedule, not just Madrid meetings.
                        results.append(record_job(client, f"team:{opponent_id}", lambda: client.get_team_matches(opponent_id), lambda db, p: ingest_matches(db, match_rows(p))))
                    # Rotate through unresolved older Madrid fixtures, including
                    # prior seasons that are absent from the current-season feed.
                    with SessionLocal() as db:
                        ids = list(db.scalars(select(Match.external_id).where(
                            or_(Match.home_team.has(Team.external_id == 86), Match.away_team.has(Team.external_id == 86)),
                            Match.status.not_in(("FINISHED", "CANCELLED", "AWARDED")),
                            Match.utc_date < utc_now() - timedelta(hours=6)
                        ).order_by(Match.updated_at.asc().nullsfirst(), Match.id).limit(3)))
                    for external in ids:
                        results.append(record_job(client, "reconcile", lambda e=external: client.get(f"/matches/{e}"), lambda db, p: ingest_matches(db, [p])))
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
            lock.commit()
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    interval = max(300, int(os.getenv("INGEST_INTERVAL_SECONDS", "600")))
    while not stop.is_set():
        try:
            runs = run_once()
            failed = any(r.status == "failed" for r in runs)
        except Exception as exc:
            log.error("worker cycle failed error=%s", type(exc).__name__)
            failed = True
        if args.once:
            return int(failed)
        stop.wait(interval)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
