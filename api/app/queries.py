from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Competition, IngestionRun, Match, Season, Standing, Team, utc_now

REAL_MADRID_EXTERNAL_ID = 86
LA_LIGA_CODE = "PD"


def get_real_madrid(db: Session) -> Team | None:
    """Use the provider identity, never a database-local or model-supplied id."""
    return db.scalar(select(Team).where(Team.external_id == REAL_MADRID_EXTERNAL_ID))


def get_latest_standings_season(
    db: Session, competition_code: str = LA_LIGA_CODE
) -> Season | None:
    return db.scalar(
        select(Season)
        .join(Season.competition)
        .where(Competition.code == competition_code, Season.standings.any())
        .options(selectinload(Season.competition))
        .order_by(Season.end_date.desc(), Season.id.desc())
        .limit(1)
    )

_MATCH_TEAM_LOAD = (
    selectinload(Match.home_team),
    selectinload(Match.away_team),
    selectinload(Match.competition),
    selectinload(Match.season),
)


def _team_matches_statement(
    team_id: int,
    *,
    status: str | None = None,
    statuses: tuple[str, ...] | None = None,
    after: datetime | None = None,
    competition_code: str | None = None,
    season_label: str | None = None,
):
    stmt = select(Match).where(
        or_(Match.home_team_id == team_id, Match.away_team_id == team_id)
    )
    if status is not None:
        stmt = stmt.where(Match.status == status)
    if statuses is not None:
        stmt = stmt.where(Match.status.in_(statuses))
    if after is not None:
        stmt = stmt.where(Match.utc_date >= after)
    if competition_code is not None:
        stmt = stmt.where(Match.competition.has(Competition.code == competition_code))
    if season_label is not None:
        stmt = stmt.where(Match.season.has(Season.year_label == season_label))
    return stmt


def list_teams(db: Session) -> list[Team]:
    return list(db.scalars(select(Team).order_by(Team.name)).all())


def get_team(db: Session, id: int) -> Team | None:
    return db.get(Team, id)


def get_team_matches(
    db: Session,
    team_id: int,
    limit: int = 10,
    status: str | None = None,
    *,
    statuses: tuple[str, ...] | None = None,
    after: datetime | None = None,
    competition_code: str | None = None,
    season_label: str | None = None,
    ascending: bool = False,
    offset: int = 0,
) -> list[Match]:
    stmt = (
        _team_matches_statement(
            team_id, status=status, statuses=statuses, after=after,
            competition_code=competition_code, season_label=season_label,
        )
        .options(*_MATCH_TEAM_LOAD)
        .order_by(Match.utc_date.asc() if ascending else Match.utc_date.desc(), Match.id)
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def get_madrid_match_page(
    db: Session,
    *,
    view: str = "upcoming",
    competition_code: str | None = None,
    season: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """A paginated Madrid-only snapshot, using the same match query as Ask Echo."""
    team = get_real_madrid(db)
    result = dict(team=team, matches=[], competitions=[], seasons=[],
                  selected_season=None, imported_at=None, total=0, limit=limit,
                  offset=offset, has_more=False)
    if team is None:
        return result
    team_filter = or_(Match.home_team_id == team.id, Match.away_team_id == team.id)
    seasons = list(db.scalars(
        select(Season).where(Season.matches.any(team_filter))
        .order_by(Season.start_date.desc(), Season.id.desc())
    ).all())
    labels = list(dict.fromkeys(row.year_label for row in seasons))
    result["seasons"] = labels
    selected = (labels[0] if labels else None) if season is None else (
        None if season == "all" else season
    )
    result["selected_season"] = selected
    result["competitions"] = list(db.scalars(
        select(Competition).where(Competition.matches.any(team_filter))
        .order_by(Competition.name)
    ).all())
    # This is the last successful match import, not a claim of live scores.
    result["imported_at"] = db.scalar(
        select(IngestionRun.finished_at)
        .where(IngestionRun.source == "football-data.org",
               IngestionRun.entity_type == "match", IngestionRun.status == "success",
               IngestionRun.finished_at.is_not(None))
        .order_by(IngestionRun.finished_at.desc()).limit(1)
    )
    filters = dict(
        competition_code=competition_code, season_label=selected,
        statuses=("SCHEDULED", "TIMED") if view == "upcoming" else (
            ("FINISHED",) if view == "results" else None
        ),
        after=utc_now() if view == "upcoming" else None,
    )
    stmt = _team_matches_statement(team.id, **filters)
    result["total"] = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    result["matches"] = get_team_matches(
        db, team.id, limit=limit, offset=offset, ascending=view == "upcoming", **filters
    )
    result["has_more"] = offset + len(result["matches"]) < result["total"]
    return result


def list_competitions(db: Session) -> list[Competition]:
    return list(db.scalars(select(Competition).order_by(Competition.name)).all())


def get_match(db: Session, id: int) -> Match | None:
    return db.get(Match, id, options=_MATCH_TEAM_LOAD)


def find_team_by_name(db: Session, name: str) -> Team | None:
    needle = name.strip()
    if not needle:
        return None
    exact = db.scalar(
        select(Team).where(
            or_(
                func.lower(Team.name) == needle.lower(),
                func.lower(Team.short_name) == needle.lower(),
            )
        )
    )
    if exact is not None:
        return exact
    return db.scalar(
        select(Team)
        .where(
            or_(
                Team.name.ilike(f"%{needle}%"),
                Team.short_name.ilike(f"%{needle}%"),
            )
        )
        .order_by(Team.name)
        .limit(1)
    )


def get_standings(
    db: Session,
    limit: int | None = None,
    team_id: int | None = None,
    competition_code: str = LA_LIGA_CODE,
    season_id: int | None = None,
) -> list[Standing]:
    # Both REST and Ask Echo default to the latest populated La Liga season.
    season = get_latest_standings_season(db, competition_code)
    if season is None:
        return []
    if season_id is not None and season_id != season.id:
        return []
    stmt = (
        select(Standing)
        .options(selectinload(Standing.team))
        .order_by(Standing.position)
    )
    stmt = stmt.where(Standing.season_id == season.id)
    if team_id is not None:
        stmt = stmt.where(Standing.team_id == team_id)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def get_team_standing(db: Session, team_id: int) -> Standing | None:
    rows = get_standings(db, team_id=team_id, limit=1)
    return rows[0] if rows else None
