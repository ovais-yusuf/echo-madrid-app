from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TeamRef(BaseModel):
    """Nested team on match responses: id + name only."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: str | None
    crest_url: str | None


class CompetitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str | None
    type: str | None


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    utc_date: datetime
    status: str
    home_team: TeamRef
    away_team: TeamRef
    home_score: int | None
    away_score: int | None
    matchday: int | None


class StandingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    team: TeamRef
    played: int
    won: int
    drawn: int
    lost: int
    points: int
    goals_for: int
    goals_against: int


class StandingTableRow(StandingRead):
    team: TeamRead
    is_real_madrid: bool


class StandingsSeasonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year_label: str
    start_date: date
    end_date: date


class StandingsResponse(BaseModel):
    competition: CompetitionRead | None
    season: StandingsSeasonRead | None
    updated_at: datetime | None
    standings: list[StandingTableRow]


class MatchCardRead(MatchRead):
    home_team: TeamRead
    away_team: TeamRead
    competition: CompetitionRead
    season: StandingsSeasonRead


class MatchesResponse(BaseModel):
    team: TeamRead | None
    matches: list[MatchCardRead]
    competitions: list[CompetitionRead]
    seasons: list[str]
    selected_season: str | None
    imported_at: datetime | None
    total: int
    limit: int
    offset: int
    has_more: bool


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any]


class AskResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallRecord]
