from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import queries
from app.main import app
from app.models import Competition, IngestionRun, Match, Season, Team

NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


@pytest.fixture
def match_data(db, monkeypatch):
    monkeypatch.setattr(queries, "utc_now", lambda: NOW)
    madrid = Team(id=41, external_id=86, name="Real Madrid CF", short_name="Real Madrid")
    opponent = Team(id=2, external_id=81, name="Opponent", short_name=None)
    third = Team(id=3, external_id=10, name="Third club", short_name=None)
    liga = Competition(id=1, external_id=2014, name="La Liga", code="PD")
    cl = Competition(id=2, external_id=2001, name="Champions League", code="CL")
    db.add_all([madrid, opponent, third, liga, cl]); db.flush()
    seasons = [
        Season(id=1, external_id=1, competition_id=liga.id, year_label="2026/2027", start_date=date(2026, 8, 1), end_date=date(2027, 6, 1)),
        Season(id=2, external_id=2, competition_id=cl.id, year_label="2026/2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 1)),
        Season(id=3, external_id=3, competition_id=liga.id, year_label="2025/2026", start_date=date(2025, 8, 1), end_date=date(2026, 6, 1)),
    ]
    db.add_all(seasons); db.flush()

    def add(id, status, day, *, season_id=1, home=41, away=2, home_score=None, away_score=None):
        season = next(s for s in seasons if s.id == season_id)
        db.add(Match(id=id, external_id=id, competition_id=season.competition_id,
            season_id=season_id, utc_date=datetime(2026, 10, day, 20, tzinfo=timezone.utc),
            status=status, home_team_id=home, away_team_id=away,
            home_score=home_score, away_score=away_score))
    add(1, "FINISHED", 10, home_score=3, away_score=1)
    add(2, "FINISHED", 12, home=2, away=41, home_score=1, away_score=1)
    add(3, "TIMED", 20)
    add(4, "SCHEDULED", 18, season_id=2)
    add(5, "SCHEDULED", 3)  # stale scheduled date must not appear as upcoming
    add(6, "POSTPONED", 19)
    add(7, "CANCELED", 22)
    add(8, "FINISHED", 14, home=2, away=3, home_score=2, away_score=0)  # not Madrid
    add(9, "FINISHED", 15, season_id=3, home_score=2, away_score=0)
    add(10, "IN_PLAY", 16, home_score=1, away_score=0)
    db.add_all([
        IngestionRun(source="football-data.org", entity_type="match", status="success", finished_at=datetime(2026, 10, 15, 10, tzinfo=timezone.utc), records_upserted=9),
        IngestionRun(source="football-data.org", entity_type="match", status="failed", finished_at=NOW, records_upserted=0),
        IngestionRun(source="football-data.org", entity_type="standing", status="success", finished_at=NOW, records_upserted=20),
    ])
    db.commit()
    return madrid


def test_missing_madrid_is_explicit(db):
    with TestClient(app) as client:
        response = client.get("/matches")
    assert response.status_code == 200
    data = response.json()
    assert data["matches"] == [] and data["team"] is None
    assert data["total"] == 0 and data["has_more"] is False


def test_upcoming_timed_and_scheduled_nearest_first(db, match_data):
    with TestClient(app) as client:
        data = client.get("/matches").json()
    assert [m["id"] for m in data["matches"]] == [4, 3]
    assert data["total"] == 2
    assert data["team"]["id"] == 41
    assert data["selected_season"] == "2026/2027"
    assert data["seasons"] == ["2026/2027", "2025/2026"]
    assert {c["code"] for c in data["competitions"]} == {"PD", "CL"}
    assert data["matches"][0]["competition"]["code"] == "CL"
    assert data["matches"][0]["home_score"] is None
    assert data["imported_at"].startswith("2026-10-15T10:00:00")


def test_results_only_finished_madrid_newest_first(db, match_data):
    with TestClient(app) as client:
        data = client.get("/matches?view=results").json()
    assert [m["id"] for m in data["matches"]] == [2, 1]
    assert data["matches"][0]["away_team"]["id"] == 41
    assert data["matches"][0]["home_score"] == 1


def test_filters_and_pagination_use_same_count(db, match_data):
    with TestClient(app) as client:
        first = client.get("/matches?view=results&competition=PD&limit=1").json()
        second = client.get("/matches?view=results&competition=PD&limit=1&offset=1").json()
        cl = client.get("/matches?competition=CL").json()
        old = client.get("/matches?view=results&season=2025%2F2026").json()
        all_seasons = client.get("/matches?view=results&season=all").json()
    assert first["total"] == 2 and first["has_more"] is True
    assert [m["id"] for m in first["matches"]] == [2]
    assert [m["id"] for m in second["matches"]] == [1] and second["has_more"] is False
    assert [m["id"] for m in cl["matches"]] == [4]
    assert [m["id"] for m in old["matches"]] == [9]
    assert [m["id"] for m in all_seasons["matches"]] == [9, 2, 1]
    assert all_seasons["selected_season"] is None


def test_all_view_keeps_postponed_cancelled_and_stale_statuses(db, match_data):
    with TestClient(app) as client:
        data = client.get("/matches?view=all").json()
        unknown = client.get("/matches?view=all&competition=UNKNOWN").json()
    assert [m["id"] for m in data["matches"]] == [7, 3, 6, 4, 10, 2, 1, 5]
    assert unknown["matches"] == [] and unknown["total"] == 0
    assert data["total"] == 8


@pytest.mark.parametrize("query", ["view=bad", "limit=0", "limit=101", "offset=-1", "season=" + "x" * 21])
def test_bad_parameters_are_rejected(db, query):
    with TestClient(app) as client:
        assert client.get(f"/matches?{query}").status_code == 422


def test_existing_match_routes_and_shared_query_still_work(db, match_data):
    with TestClient(app) as client:
        response = client.get("/matches/1")
        team_matches = client.get("/teams/41/matches?status=FINISHED&limit=2").json()
    assert response.status_code == 200
    assert response.json()["home_score"] == 3
    assert [m["id"] for m in team_matches] == [9, 2]
