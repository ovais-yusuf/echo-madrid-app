"""Ingest the current La Liga table from football-data.org into Postgres."""

from __future__ import annotations

import logging
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competition, IngestionRun, Season, Standing, StandingsSnapshot, Team, utc_now
from pipeline.ingest_matches import (
    upsert_competition,
    upsert_season,
    upsert_team,
)

logger = logging.getLogger(__name__)

SOURCE = "football-data.org"
ENTITY_TYPE = "standing"
LA_LIGA_CODE = "PD"


def upsert_standing(
    session: Session,
    season_id: int,
    team_id: int,
    row: dict[str, Any],
) -> Standing:
    existing = session.scalar(
        select(Standing).where(
            Standing.season_id == season_id,
            Standing.team_id == team_id,
        )
    )
    fields = {
        "stage": row.get("stage"),
        "group_name": row.get("group_name"),
        "position": row["position"],
        "played": row["playedGames"],
        "won": row["won"],
        "drawn": row["draw"],
        "lost": row["lost"],
        "points": row["points"],
        "goals_for": row["goalsFor"],
        "goals_against": row["goalsAgainst"],
        "updated_at": utc_now(),
    }
    if existing is None:
        standing = Standing(season_id=season_id, team_id=team_id, **fields)
        session.add(standing)
        session.flush()
        return standing
    for key, value in fields.items():
        setattr(existing, key, value)
    return existing


def _total_tables(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for standing in payload.get("standings") or []:
        if standing.get("type") == "TOTAL":
            tables.extend({**row, "stage": standing.get("stage"), "group_name": standing.get("group")} for row in standing.get("table") or [])
    return tables


def ingest_standings(session: Session, payload: dict[str, Any]) -> int:
    competitions: dict[int, Competition] = {}
    seasons: dict[int, Season] = {}
    teams: dict[int, Team] = {}

    competition = upsert_competition(session, payload["competition"], competitions)
    season = upsert_season(session, payload["season"], competition.id, seasons)

    rows = _total_tables(payload)
    if not rows:
        raise RuntimeError("Standings payload had no TOTAL table")

    identities = [row["team"]["id"] for row in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("Multiple standings stages for one team are not supported; retaining last table")
    previous = session.scalar(select(StandingsSnapshot).where(
        StandingsSnapshot.season_id == season.id
    ).order_by(StandingsSnapshot.id.desc()).limit(1))
    if previous is None or previous.rows != rows:
        session.add(StandingsSnapshot(season_id=season.id, rows=rows))
    # Remove rows absent from an authoritative replacement, within the same transaction.
    current_ids = []
    for row in rows:
        team = upsert_team(session, row["team"], teams)
        upsert_standing(session, season.id, team.id, row)
        current_ids.append(team.id)
    from sqlalchemy import delete
    session.execute(delete(Standing).where(Standing.season_id == season.id, Standing.team_id.not_in(current_ids)))
    return len(rows)


def run_ingestion() -> IngestionRun:
    from pipeline.worker import run_once
    return run_once(only="standing:PD")[0]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run = run_ingestion()
    if run.status == "success":
        print(
            f"Ingestion complete: {run.records_upserted} standings upserted "
            f"(status={run.status})"
        )
        return 0
    print(
        f"Ingestion failed: {run.error} "
        f"(status={run.status}, standings upserted={run.records_upserted})"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
