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
    candidates = list(db.scalars(
        select(Team).where(or_(Team.name.ilike(f"%{needle}%"), Team.short_name.ilike(f"%{needle}%")))
        .order_by(Team.name).limit(2)
    ))
    return candidates[0] if len(candidates) == 1 else None


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


def freshness(db: Session, entity: str, max_age_seconds: int = 1800) -> dict:
    from datetime import timezone
    stmt = select(IngestionRun).where(IngestionRun.source == "football-data.org", IngestionRun.entity_type == entity)
    last = db.scalar(stmt.order_by(IngestionRun.started_at.desc()).limit(1))
    success = db.scalar(stmt.where(IngestionRun.status == "success").order_by(IngestionRun.finished_at.desc()).limit(1))
    timestamp = success.finished_at if success else None
    if timestamp and timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age = max(0, int((utc_now() - timestamp).total_seconds())) if timestamp else None
    stale = age is None or age > max_age_seconds
    return {"source": "football-data.org", "last_success": timestamp.isoformat() if timestamp else None,
            "age_seconds": age, "stale": stale, "last_attempt_status": last.status if last else "never",
            "access_issue": bool(last and last.error in ("HTTPStatusError:401", "HTTPStatusError:403")),
            "message": "Freshness unverified: no successful import recorded." if timestamp is None else (
                "Stored data is stale; results and schedules may have changed." if stale else
                "Automatically refreshed snapshot. Provider scores and schedules may be delayed; not live scores.")}


def match_record(match: Match | None):
    from app.schemas import MatchCardRead
    return MatchCardRead.model_validate(match).model_dump(mode="json") if match else None


def team_record(db: Session, team: Team, *, limit: int = 5, venue: str = "all",
                season: str | None = None, opponent: str | None = None) -> dict:
    # A named opponent without its own ingestion cannot have inferred overall form.
    entity = "match" if team.external_id == 86 else f"team:{team.external_id}"
    coverage = freshness(db, entity)
    if team.external_id != 86 and coverage["last_success"] is None:
        return {"team": team.name, "available": False, "matches": [], "count": 0,
                "freshness": coverage, "reason": "Opponent's own match history has not been imported."}
    stmt = _team_matches_statement(team.id, status="FINISHED", season_label=season)
    stmt = stmt.where(Match.home_score.is_not(None), Match.away_score.is_not(None))
    if venue == "home":
        stmt = stmt.where(Match.home_team_id == team.id)
    elif venue == "away":
        stmt = stmt.where(Match.away_team_id == team.id)
    if opponent:
        other = find_team_by_name(db, opponent)
        if not other:
            return {"team": team.name, "available": False, "matches": [], "count": 0, "reason": "Opponent not found."}
        stmt = stmt.where(or_(Match.home_team_id == other.id, Match.away_team_id == other.id))
    matches = list(db.scalars(stmt.options(*_MATCH_TEAM_LOAD).order_by(Match.utc_date.desc(), Match.id.desc()).limit(limit)))
    stats = dict(won=0, drawn=0, lost=0, goals_for=0, goals_against=0, clean_sheets=0)
    form = []
    progress = []
    points = 0
    for m in reversed(matches):
        gf, ga = (m.home_score, m.away_score) if m.home_team_id == team.id else (m.away_score, m.home_score)
        outcome = "W" if gf > ga else "L" if gf < ga else "D"
        stats[{"W": "won", "D": "drawn", "L": "lost"}[outcome]] += 1
        stats["goals_for"] += gf
        stats["goals_against"] += ga
        stats["clean_sheets"] += ga == 0
        points += 3 if outcome == "W" else 1 if outcome == "D" else 0
        form.append(outcome)
        progress.append({"date": m.utc_date.isoformat(), "goals_for": gf, "goals_against": ga, "cumulative_result_points": points})
    return {"available": bool(matches), "team": team.name, "venue": venue, "season": season,
            "count": len(matches), "requested_count": limit, "period_start": matches[-1].utc_date.isoformat() if matches else None,
            "period_end": matches[0].utc_date.isoformat() if matches else None, "form_oldest_first": form,
            **stats, "matches": [match_record(m) for m in matches], "progress": progress, "freshness": coverage,
            "scope": "Available completed provider matches with scores; may exclude uncovered competitions. Result points are a trend, not official league points."}


def matchday(db: Session) -> dict:
    from datetime import timedelta
    team = get_real_madrid(db)
    data = {"current": None, "next": None, "latest": None, "unresolved": [], "freshness": freshness(db, "match")}
    if not team:
        return data
    current = get_team_matches(db, team.id, statuses=("IN_PLAY", "PAUSED", "EXTRA_TIME", "PENALTY_SHOOTOUT"), after=utc_now() - timedelta(hours=6), limit=1)
    upcoming = get_team_matches(db, team.id, statuses=("SCHEDULED", "TIMED"), after=utc_now(), ascending=True, limit=1)
    latest = get_team_matches(db, team.id, status="FINISHED", limit=1)
    unresolved = list(db.scalars(_team_matches_statement(team.id).where(
        Match.utc_date < utc_now(), Match.utc_date >= utc_now() - timedelta(days=14),
        Match.status.not_in(("FINISHED",))
    ).options(*_MATCH_TEAM_LOAD).order_by(Match.utc_date.desc()).limit(10)))
    data.update(current=match_record(current[0]) if current else None,
                next=match_record(upcoming[0]) if upcoming else None,
                latest=match_record(latest[0]) if latest else None,
                unresolved=[match_record(m) for m in unresolved if not current or m.id != current[0].id])
    return data


def opponent_preview(db: Session):
    centre = matchday(db)
    fixture = centre["current"] or centre["next"]
    madrid = get_real_madrid(db)
    if not fixture or not madrid:
        return {"available": False, "reason": "No current or upcoming fixture available."}
    other_id = fixture["away_team"]["id"] if fixture["home_team"]["id"] == madrid.id else fixture["home_team"]["id"]
    other = get_team(db, other_id)
    home = fixture["home_team"]["id"] == madrid.id
    meetings = list(db.scalars(_team_matches_statement(madrid.id, status="FINISHED").where(
        or_(Match.home_team_id == other_id, Match.away_team_id == other_id)
    ).options(*_MATCH_TEAM_LOAD).order_by(Match.utc_date.desc()).limit(5)))
    return {"available": True, "fixture": fixture, "madrid": team_record(db, madrid),
            "opponent": team_record(db, other),
            "madrid_venue": team_record(db, madrid, venue="home" if home else "away"),
            "opponent_venue": team_record(db, other, venue="away" if home else "home"),
            "previous_meetings": [match_record(m) for m in meetings]}


def standings_changes(db: Session, code: str):
    from app.models import StandingsSnapshot
    season = get_latest_standings_season(db, code)
    snapshots = list(db.scalars(select(StandingsSnapshot).where(StandingsSnapshot.season_id == season.id)
                    .order_by(StandingsSnapshot.id.desc()).limit(2))) if season else []
    if len(snapshots) < 2:
        return {"available": False, "reason": "Two real, changed snapshots are needed; no history has been invented."}
    new, old = snapshots
    prior = {r["team"]["id"]: r for r in old.rows}
    changes = [{"team": r["team"]["name"], "position_change": prior[r["team"]["id"]]["position"] - r["position"],
                "points_change": r["points"] - prior[r["team"]["id"]]["points"]}
               for r in new.rows if r["team"]["id"] in prior]
    matches = list(db.scalars(select(Match).where(Match.competition.has(Competition.code == code),
        Match.status == "FINISHED", Match.utc_date >= old.captured_at, Match.utc_date <= new.captured_at)
        .options(*_MATCH_TEAM_LOAD).order_by(Match.utc_date.desc())))
    return {"available": True, "from": old.captured_at, "to": new.captured_at, "changes": changes,
            "results_in_interval": [match_record(m) for m in matches],
            "note": "Observed table differences; listed results kicked off in this interval. Corrections, deductions and delayed updates may also affect the table; causation is not inferred."}
