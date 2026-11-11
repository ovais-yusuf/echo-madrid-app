from copy import deepcopy
from datetime import timedelta, timezone
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.main import app
from app.models import Match, Season, Team, Standing, StandingsSnapshot, IngestionRun, utc_now
from app.queries import freshness, team_record, matchday, opponent_preview, standings_changes
from app.exports import calendar_event
from pipeline.ingest_matches import ingest_matches, FootballDataClient
from pipeline.ingest_standings import ingest_standings
from pipeline.worker import record_job, match_rows


def fixture(status="FINISHED", home=2, away=0, ident=1, when=None, year=2026):
    return {"id": ident, "competition": {"id": 2014, "name": "La Liga", "code": "PD"},
            "season": {"id": year, "startDate": f"{year}-08-01", "endDate": f"{year+1}-06-01"},
            "homeTeam": {"id": 86, "name": "Real Madrid"}, "awayTeam": {"id": 81, "name": "Opponent"},
            "utcDate": (when or utc_now()-timedelta(days=1)).isoformat(), "status": status,
            "score": {"fullTime": {"home": home, "away": away}}, "matchday": 1}


def table(points=3, code="PD", year=2026):
    return {"competition": {"id": 2014 if code == "PD" else 2001, "name": code, "code": code},
            "season": {"id": year if code == "PD" else year+100, "startDate": f"{year}-08-01", "endDate": f"{year+1}-06-01"},
            "standings": [{"type": "TOTAL", "stage": "LEAGUE_STAGE" if code == "CL" else "REGULAR_SEASON", "group": None,
            "table": [{"team": {"id": 86, "name": "Real Madrid"}, "position": 1, "playedGames": 1,
                       "won": 1, "draw": 0, "lost": 0, "points": points, "goalsFor": 2, "goalsAgainst": 0}]}]}


def success(db, entity, age=0):
    db.add(IngestionRun(source="football-data.org", entity_type=entity, status="success", records_upserted=1,
                        started_at=utc_now()-timedelta(seconds=age+1), finished_at=utc_now()-timedelta(seconds=age)))
    db.commit()


def test_upsert_status_score_reschedule_and_rollover(db):
    p = fixture("TIMED", None, None)
    ingest_matches(db,[p]); db.commit()
    p.update(status="POSTPONED", utcDate=(utc_now()+timedelta(days=10)).isoformat())
    ingest_matches(db,[p]); db.commit()
    row=db.scalar(select(Match)); assert row.status == "POSTPONED" and row.home_score is None
    p.update(status="FINISHED", score={"fullTime":{"home":3,"away":2}})
    ingest_matches(db,[p]); ingest_matches(db,[fixture(ident=2,year=2027)]); db.commit()
    assert db.scalar(select(func.count()).select_from(Match)) == 2
    assert db.scalar(select(func.count()).select_from(Season)) == 2
    assert row.home_score == 3 and row.away_score == 2 and row.updated_at


def test_standings_snapshot_idempotency_formats_and_seasons(db):
    ingest_standings(db,table()); db.commit()
    ingest_standings(db,table()); db.commit()
    assert db.scalar(select(func.count()).select_from(StandingsSnapshot)) == 1
    ingest_standings(db,table(points=6)); db.commit()
    assert standings_changes(db,"PD")["changes"][0]["points_change"] == 3
    ingest_standings(db,table(code="CL")); db.commit()
    with TestClient(app) as client:
        assert client.get('/standings?competition=CL').json()['standings'][0]['stage'] == 'LEAGUE_STAGE'
        assert client.get('/standings?competition=PD').json()['standings'][0]['points'] == 6
        assert client.get('/standings?competition=INVALID').status_code == 422
    ingest_standings(db,table(year=2027)); db.commit()
    assert not standings_changes(db,"PD")["available"]


def test_freshness_is_separate_and_failure_keeps_success(db):
    assert freshness(db,"match")["stale"]
    success(db,"match",3600); success(db,"standing:PD",5)
    db.add(IngestionRun(source="football-data.org",entity_type="match",status="failed",started_at=utc_now(), finished_at=utc_now()))
    db.commit()
    assert freshness(db,"match")["stale"]
    assert freshness(db,"match")["last_success"]
    assert freshness(db,"match")["last_attempt_status"] == "failed"
    assert not freshness(db,"standing:PD")["stale"]
    assert freshness(db,"standing:CL")["stale"]


@pytest.mark.parametrize("status",["IN_PLAY","PAUSED","EXTRA_TIME","PENALTY_SHOOTOUT"])
def test_current_states(db,status):
    ingest_matches(db,[fixture(status,1,0,when=utc_now()-timedelta(minutes=45))]); db.commit()
    assert matchday(db)["current"]["status"] == status


@pytest.mark.parametrize("status",["TIMED","SCHEDULED","POSTPONED","CANCELLED","SUSPENDED","IN_PLAY"])
def test_past_nonfinal_does_not_disappear_or_invent_result(db,status):
    ingest_matches(db,[fixture(status,None,None)]); db.commit()
    data=matchday(db)
    assert data["latest"] is None and data["current"] is None
    assert data["unresolved"][0]["status"] == status


def test_team_record_and_opponent_coverage(db):
    p=fixture(); away=fixture(ident=2, home=1,away=1); away['homeTeam'],away['awayTeam']=away['awayTeam'],away['homeTeam']
    ingest_matches(db,[p,away,fixture('TIMED',None,None,ident=3,when=utc_now()+timedelta(days=2))]); db.commit()
    team=db.scalar(select(Team).where(Team.external_id==86))
    stats=team_record(db,team)
    assert (stats['count'],stats['won'],stats['drawn'],stats['goals_for'],stats['goals_against'],stats['clean_sheets']) == (2,1,1,3,1,1)
    assert team_record(db,team,venue='away')['count']==1
    assert not opponent_preview(db)['opponent']['available']
    success(db,'team:81')
    assert opponent_preview(db)['opponent']['available']
    assert team_record(db,team,season='2027/2028')['count']==0


def test_retries_and_permanent_errors(monkeypatch):
    monkeypatch.setattr('pipeline.ingest_matches.time.sleep',lambda _:None)
    with FootballDataClient('test-only') as client:
        client._limiter.wait=Mock()
        request=httpx.Request('GET','https://example.test')
        client._client.get=Mock(side_effect=[httpx.Response(429,request=request,headers={'Retry-After':'1'}),httpx.Response(503,request=request),httpx.Response(200,request=request,json={'ok':True})])
        assert client.get('/test') == {'ok':True}
        assert client._client.get.call_count==3
        client._client.get=Mock(return_value=httpx.Response(403,request=request))
        with pytest.raises(httpx.HTTPStatusError): client.get('/test')
        assert client._client.get.call_count==1


def test_retry_budget_and_long_retry_after(monkeypatch):
    monkeypatch.setattr('pipeline.ingest_matches.time.sleep',lambda _:None)
    with FootballDataClient('test-only') as client:
        client._limiter.wait=Mock()
        client._client.get=Mock(side_effect=httpx.ReadTimeout('timeout'))
        with pytest.raises(httpx.ReadTimeout): client.get('/test')
        assert client._client.get.call_count==4
        client._client.get=Mock(return_value=httpx.Response(429,request=httpx.Request('GET','https://example.test'),headers={'Retry-After':'1000'}))
        with pytest.raises(httpx.HTTPStatusError): client.get('/test')
        assert client._client.get.call_count==1


def test_empty_payload_not_a_success():
    with pytest.raises(ValueError): match_rows({'matches':[]})


def test_job_rolls_back_partial_data_and_keeps_old_values(db,monkeypatch):
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr('pipeline.worker.SessionLocal',sessionmaker(bind=db.get_bind()))
    ingest_matches(db,[fixture()]); db.commit()
    def fail(session,payload):
        ingest_matches(session,[fixture(home=9)])
        raise ValueError('test failure')
    run=record_job(None,'match',lambda:{},fail)
    db.expire_all()
    assert run.status=='failed'
    assert db.scalar(select(Match)).home_score==2


def test_calendar_stable_id_escaping_and_postponed(db):
    ingest_matches(db,[fixture('POSTPONED',None,None)]); db.commit()
    m=db.scalar(select(Match)); m.home_team.name='Real, Madrid; test\\name\nother'
    text=calendar_event(m)
    assert 'UID:football-data-1@echo-madrid' in text and 'STATUS:CANCELLED' in text
    assert 'Real\\, Madrid\\; test\\\\name\\nother' in text
    assert all(len(line.encode())<=75 for line in text.split('\r\n'))


def test_visitors_only_read_database(db, monkeypatch):
    monkeypatch.setattr(FootballDataClient,'get',Mock(side_effect=AssertionError('Visitor fetched provider')))
    ingest_matches(db,[fixture(),fixture('TIMED',None,None,ident=2,when=utc_now()+timedelta(days=2))]); db.commit()
    with TestClient(app) as client:
        for path in ['/freshness','/matchday','/preview','/analytics','/standings-changes','/matches','/standings']:
            assert client.get(path).status_code==200


def test_empty_and_ambiguous_standings_keep_last_table(db):
    ingest_standings(db,table()); db.commit()
    broken=table(); broken['standings']=[]
    with pytest.raises(RuntimeError): ingest_standings(db,broken)
    db.rollback()
    duplicate=table(); duplicate['standings']*=2
    with pytest.raises(ValueError): ingest_standings(db,duplicate)
    db.rollback()
    assert db.scalar(select(Standing)).points==3
    assert db.scalar(select(func.count()).select_from(StandingsSnapshot))==1
