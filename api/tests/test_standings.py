from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models import Competition, Season, Standing, Team
from app.queries import get_standings


def add_season(db, code, start_year, external_id):
    competition = Competition(external_id=external_id, name=code, code=code)
    db.add(competition)
    db.flush()
    season = Season(
        external_id=external_id,
        competition_id=competition.id,
        year_label=f"{start_year}/{start_year + 1}",
        start_date=date(start_year, 8, 1), end_date=date(start_year + 1, 6, 1),
    )
    db.add(season)
    db.flush()
    return season


def add_row(db, season, team, position, points):
    db.add(Standing(
        season_id=season.id, team_id=team.id, position=position, played=10,
        won=points // 3, drawn=points % 3, lost=10 - points // 3 - points % 3,
        points=points, goals_for=20, goals_against=10,
        updated_at=datetime(2026, 10, 15, 12, tzinfo=timezone.utc),
    ))
    db.flush()


def test_empty_database_is_explicit(db):
    with TestClient(app) as client:
        response = client.get("/standings")
    assert response.status_code == 200
    assert response.json() == {
        "competition": None, "season": None, "updated_at": None, "standings": []
    }


def test_latest_populated_la_liga_only_and_madrid_identity(db):
    old = add_season(db, "PD", 2025, 1)
    new = Season(external_id=2, competition_id=old.competition_id,
                 year_label="2026/2027", start_date=date(2026, 8, 1), end_date=date(2027, 6, 1))
    empty_future = Season(external_id=3, competition_id=old.competition_id,
                         year_label="2027/2028", start_date=date(2027, 8, 1), end_date=date(2028, 6, 1))
    cl = add_season(db, "CL", 2029, 4)
    db.add_all([new, empty_future])
    # Madrid deliberately does not have database-local id 2.
    madrid = Team(id=41, external_id=86, name="Real Madrid CF", short_name="Real Madrid")
    other = Team(id=2, external_id=81, name="Other club", short_name=None)
    db.add_all([madrid, other]); db.flush()
    add_row(db, old, madrid, 5, 18)
    add_row(db, new, madrid, 2, 24)
    add_row(db, new, other, 1, 27)
    add_row(db, cl, madrid, 1, 30)
    db.commit()
    with TestClient(app) as client:
        response = client.get("/standings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["competition"]["code"] == "PD"
    assert payload["season"]["year_label"] == "2026/2027"
    assert payload["updated_at"].startswith("2026-10-15T12:00:00")
    assert [row["position"] for row in payload["standings"]] == [1, 2]
    assert [row["is_real_madrid"] for row in payload["standings"]] == [False, True]
    assert payload["standings"][1]["team"]["id"] == 41
    assert [row.points for row in get_standings(db)] == [27, 24]
    assert get_standings(db, team_id=madrid.id)[0].points == 24
    assert len(get_standings(db, limit=1)) == 1


def test_other_competition_never_substitutes_for_missing_la_liga(db):
    cl = add_season(db, "CL", 2026, 10)
    madrid = Team(external_id=86, name="Real Madrid CF")
    db.add(madrid); db.flush()
    add_row(db, cl, madrid, 1, 27)
    db.commit()
    with TestClient(app) as client:
        payload = client.get("/standings").json()
    assert payload["standings"] == []
    assert get_standings(db) == []
