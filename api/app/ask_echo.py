"""Ask Echo: natural-language answers grounded on local match and standings data."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_openai_api_key
from app.models import utc_now
from app.queries import find_team_by_name, get_real_madrid, get_standings, get_team_matches, team_record, freshness
from app.schemas import MatchRead, StandingRead, ToolCallRecord

NO_DATA_ANSWER = "I don't have that data."
DEFAULT_MATCH_LIMIT = 10
MAX_MATCH_LIMIT = 100
MAX_STANDINGS_LIMIT = 20
ALLOWED_STATUSES = frozenset({"SCHEDULED", "TIMED", "IN_PLAY", "PAUSED", "FINISHED", "POSTPONED", "CANCELLED", "SUSPENDED"})
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are Ask Echo, a Real Madrid and La Liga assistant.

You may ONLY answer from the data returned by tools. Those tools read our
local database; they are the sole source of truth.

Available tools:
- get_team_matches: Real Madrid fixtures and results (dates, opponents, scores).
- get_standings: the current La Liga table (position, points, played, W/D/L,
  goals, team names). Use this for league position, points, or table questions.
  Pass team_name to filter to one club; omit it for the full table.

Pick the tool that matches the question. You may call more than one if needed.

Rules:
- If the tool results do not contain the answer, say you do not have that data.
- Never fabricate scores, dates, opponents, positions, points, or any other stats.
- Never use prior football knowledge to fill gaps.
- If no tool was used or the rows are empty, say you do not have that data.
- Prefer concise, factual answers that cite only values present in the tool result.
"""

GET_TEAM_MATCHES_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_team_matches",
        "description": (
            "Return Real Madrid's matches from the local database, most recent "
            "first. Each row includes utc_date, status, home_team, away_team, "
            "home_score, away_score, and matchday. "
            "Use this for fixtures, results, or recent form. "
            "Optional limit (default 10). Optional status filter: SCHEDULED "
            "for upcoming fixtures or FINISHED for completed results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": (
                        "Maximum number of matches to return. Defaults to 10."
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": sorted(ALLOWED_STATUSES),
                    "description": (
                        "If set, only return matches with this status."
                    ),
                },
            },
        },
    },
}

GET_STANDINGS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_standings",
        "description": (
            "Return the current La Liga table from the local database, ordered "
            "by position. Each row includes team name, position, played, won, "
            "drawn, lost, points, goals_for, and goals_against. "
            "Use this for league position, points, or standings questions. "
            "Optional team_name filters to that club's row (e.g. "
            "'Real Madrid'). Optional limit returns the top N rows."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": (
                        "Maximum number of table rows to return, from the top. "
                        "Omit for the full table."
                    ),
                },
                "team_name": {
                    "type": "string",
                    "description": (
                        "If set, return only that team's standings row. "
                        "Match on club name (for example 'Real Madrid' or "
                        "'Barcelona'). Do not pass a numeric team id."
                    ),
                },
            },
        },
    },
}

TOOLS: list[dict[str, Any]] = [GET_TEAM_MATCHES_TOOL, GET_STANDINGS_TOOL]


def _serialize_matches(matches: list[Any]) -> list[dict[str, Any]]:
    return [MatchRead.model_validate(match).model_dump(mode="json") for match in matches]


def _serialize_standings(rows: list[Any]) -> list[dict[str, Any]]:
    return [StandingRead.model_validate(row).model_dump(mode="json") for row in rows]


class MatchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    limit: int = Field(default=10, ge=1, le=100)
    status: Literal["SCHEDULED", "TIMED", "IN_PLAY", "PAUSED", "FINISHED", "POSTPONED", "CANCELLED", "SUSPENDED"] | None = None


class StandingsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    limit: int | None = Field(default=None, ge=1, le=20)
    team_name: str | None = Field(default=None, min_length=1, max_length=100)


def parse_get_team_matches_args(raw_arguments: str) -> dict[str, Any]:
    parsed = json.loads(raw_arguments)
    if isinstance(parsed, dict):
        parsed.pop("team_id", None)  # Provider Madrid identity is server-owned.
    return MatchArguments.model_validate(parsed).model_dump()


def parse_get_standings_args(raw_arguments: str) -> dict[str, Any]:
    return StandingsArguments.model_validate_json(raw_arguments).model_dump()


def execute_get_team_matches(
    db: Session, arguments: dict[str, Any]
) -> list[dict[str, Any]]:
    team = get_real_madrid(db)
    if team is None:
        return []
    matches = get_team_matches(
        db,
        team.id,
        limit=arguments.get("limit", DEFAULT_MATCH_LIMIT),
        status=None if arguments.get("status") == "SCHEDULED" else arguments.get("status"),
        **({"statuses": ("SCHEDULED", "TIMED"), "after": utc_now(), "ascending": True} if arguments.get("status") == "SCHEDULED" else {}),
    )
    return _serialize_matches(matches)


def execute_get_standings(
    db: Session, arguments: dict[str, Any]
) -> list[dict[str, Any]]:
    team_id = None
    team_name = arguments.get("team_name")
    if team_name:
        team = find_team_by_name(db, team_name)
        if team is None:
            return []
        team_id = team.id
    rows = get_standings(
        db,
        limit=arguments.get("limit"),
        team_id=team_id,
    )
    return _serialize_standings(rows)


_TOOL_HANDLERS: dict[
    str,
    tuple[Callable[[str], dict[str, Any]], Callable[[Session, dict[str, Any]], Any]],
] = {
    "get_team_matches": (parse_get_team_matches_args, execute_get_team_matches),
    "get_standings": (parse_get_standings_args, execute_get_standings),
}



class RecordArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    limit: int = Field(default=5, ge=1, le=100)
    venue: Literal["all", "home", "away"] = "all"
    season: str | None = Field(default=None, max_length=20)
    opponent: str | None = Field(default=None, max_length=100)


def parse_record(raw):
    return RecordArguments.model_validate_json(raw).model_dump()


def execute_record(db, arguments):
    team = get_real_madrid(db)
    return team_record(db, team, **arguments) if team else {}


TOOLS.append({"type": "function", "function": {
    "name": "get_record", "description": "Calculate Madrid recent form, scored/conceded goals, clean sheets, home/away records and results versus a named opponent. Sample limited to covered finished matches. Use venue for follow-up questions about away or home games.",
    "parameters": RecordArguments.model_json_schema()}})
_TOOL_HANDLERS["get_record"] = (parse_record, execute_record)


def render_evidence(name, data):
    """Deterministic text: the model chooses a query but cannot invent facts."""
    if name == "get_record":
        if not data.get("available"):
            return NO_DATA_ANSWER
        return (f"{data['team']} — {data['venue']} sample: {data['count']} completed matches "
                f"({data['period_start']} to {data['period_end']}). "
                f"{data['won']} wins, {data['drawn']} draws, {data['lost']} losses; "
                f"{data['goals_for']} scored, {data['goals_against']} conceded; "
                f"{data['clean_sheets']} clean sheets. Form (oldest first): "
                + ' '.join(data['form_oldest_first']) + '. ' + data['scope'])
    if name == "get_team_matches":
        return '\n'.join(f"{r['utc_date']}: {r['home_team']['name']} "
            f"{r['home_score'] if r['home_score'] is not None else '—'}–"
            f"{r['away_score'] if r['away_score'] is not None else '—'} {r['away_team']['name']} "
            f"({r['status']})" for r in data)
    if name == "get_standings":
        return '\n'.join(f"{r['position']}. {r['team']['name']}: {r['points']} points" for r in data)
    return NO_DATA_ANSWER


def ask_echo(db: Session, question: str, history=None) -> tuple[str, list[ToolCallRecord]]:
    client = OpenAI(api_key=get_openai_api_key(), timeout=30, max_retries=1)
    messages = [{"role": "system", "content": SYSTEM_PROMPT +
                 " Use get_record for calculated statistics. Conversation history is only for intent and filters, never factual evidence. Resolve follow-ups using prior questions. Do not treat an old answer as current data."}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": question})
    first = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto")
    calls = first.choices[0].message.tool_calls or []
    if not calls:
        return NO_DATA_ANSWER, []
    records, answers = [], []
    for call in calls[:4]:
        handler = _TOOL_HANDLERS.get(call.function.name)
        arguments, payload = {}, None
        if handler:
            try:
                arguments = handler[0](call.function.arguments)
                payload = handler[1](db, arguments)
            except (ValidationError, ValueError, TypeError):
                payload = None
        clock = freshness(db, "standing:PD" if call.function.name == "get_standings" else "match")
        records.append(ToolCallRecord(name=call.function.name, arguments=arguments,
                                      evidence={"data": payload, "freshness": clock}))
        if payload and (not isinstance(payload, dict) or payload.get("available")):
            answers.append(render_evidence(call.function.name, payload) +
                           f"\nSource: football-data.org. Last successful import: {clock['last_success'] or 'unknown'}. {clock['message']}")
    return "\n\n".join(answers) or NO_DATA_ANSWER, records
