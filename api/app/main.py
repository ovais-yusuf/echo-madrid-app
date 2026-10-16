from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError
from sqlalchemy.orm import Session

from app.ask_echo import ask_echo
from app.database import get_db
from app.queries import (
    get_match as fetch_match,
    get_team as fetch_team,
    get_team_matches as fetch_team_matches,
    list_competitions as fetch_competitions,
    list_teams as fetch_teams,
    get_latest_standings_season,
    get_standings as fetch_standings,
    REAL_MADRID_EXTERNAL_ID,
    get_madrid_match_page,
)
from app.schemas import (
    AskRequest, AskResponse, CompetitionRead, MatchRead, TeamRead,
    StandingRead, StandingTableRow, StandingsResponse, StandingsSeasonRead,
    MatchesResponse,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Echo Madrid API")


@app.get("/matches", response_model=MatchesResponse)
def matches(
    view: Literal["upcoming", "results", "all"] = "upcoming",
    competition: str | None = Query(default=None, max_length=20),
    season: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> MatchesResponse:
    return MatchesResponse.model_validate(get_madrid_match_page(
        db, view=view, competition_code=competition, season=season,
        limit=limit, offset=offset,
    ))


@app.get("/standings", response_model=StandingsResponse)
def standings(db: Session = Depends(get_db)) -> StandingsResponse:
    """Latest stored La Liga table. Empty data is a valid, explicit state."""
    season = get_latest_standings_season(db)
    if season is None:
        return StandingsResponse(
            competition=None, season=None, updated_at=None, standings=[]
        )
    rows = fetch_standings(db, season_id=season.id)
    return StandingsResponse(
        competition=CompetitionRead.model_validate(season.competition),
        season=StandingsSeasonRead.model_validate(season),
        updated_at=max((row.updated_at for row in rows), default=None),
        standings=[
            StandingTableRow(
                **StandingRead.model_validate(row).model_dump(exclude={"team"}),
                team=TeamRead.model_validate(row.team),
                is_real_madrid=row.team.external_id == REAL_MADRID_EXTERNAL_ID,
            )
            for row in rows
        ],
    )


@app.get("/", include_in_schema=False)
def ask_echo_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/teams", response_model=list[TeamRead])
def list_teams(db: Session = Depends(get_db)) -> list[TeamRead]:
    return fetch_teams(db)


@app.get("/teams/{id}", response_model=TeamRead)
def get_team(id: int, db: Session = Depends(get_db)) -> TeamRead:
    team = fetch_team(db, id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team {id} not found")
    return team


@app.get("/teams/{id}/matches", response_model=list[MatchRead])
def get_team_matches(
    id: int,
    limit: int = Query(default=10, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[MatchRead]:
    if fetch_team(db, id) is None:
        raise HTTPException(status_code=404, detail=f"Team {id} not found")
    return fetch_team_matches(db, id, limit=limit, status=status)


@app.get("/competitions", response_model=list[CompetitionRead])
def list_competitions(db: Session = Depends(get_db)) -> list[CompetitionRead]:
    return fetch_competitions(db)


@app.get("/matches/{id}", response_model=MatchRead)
def get_match(id: int, db: Session = Depends(get_db)) -> MatchRead:
    match = fetch_match(db, id)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Match {id} not found")
    return match


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    try:
        answer, tool_calls = ask_echo(db, body.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail="Ask Echo failed to reach OpenAI") from exc
    return AskResponse(answer=answer, tool_calls=tool_calls)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
