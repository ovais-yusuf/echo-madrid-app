import importlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.models import Team
from app.config import normalize_database_url

module = importlib.import_module("app.ask_echo")


def completion(content=None, calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=content, tool_calls=calls
    ))])


def tool_call(name="get_standings", arguments="{}"):
    return SimpleNamespace(id="call_1", function=SimpleNamespace(name=name, arguments=arguments))


def fake_client(monkeypatch, responses):
    create = Mock(side_effect=responses)
    monkeypatch.setattr(module, "get_openai_api_key", lambda: "test-key-unused")
    monkeypatch.setattr(module, "OpenAI", lambda **kwargs: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    ))
    return create


def test_no_tool_discards_model_knowledge(db, monkeypatch):
    create = fake_client(monkeypatch, [completion("Madrid won 99 trophies.")])
    answer, calls = module.ask_echo(db, "How many trophies?")
    assert answer == "I don't have that data."
    assert calls == []
    assert create.call_count == 1


@pytest.mark.parametrize("name", ["get_standings", "unknown_tool"])
def test_empty_or_unknown_tool_skips_answer_generation(db, monkeypatch, name):
    create = fake_client(monkeypatch, [completion(calls=[tool_call(name)])])
    answer, calls = module.ask_echo(db, "Where is Madrid?")
    assert answer == module.NO_DATA_ANSWER
    assert len(calls) == 1
    assert create.call_count == 1


def test_nonempty_results_are_sent_to_answer_model(db, monkeypatch):
    rows = [{"position": 2, "points": 24, "team": {"id": 41, "name": "Real Madrid"}}]
    monkeypatch.setitem(module._TOOL_HANDLERS, "get_standings", (
        module.parse_get_standings_args, lambda session, args: rows
    ))
    create = fake_client(monkeypatch, [completion(calls=[tool_call()]), completion("Real Madrid is 2nd with 24 points.")])
    answer, calls = module.ask_echo(db, "Where is Madrid?")
    assert answer == "Real Madrid is 2nd with 24 points."
    assert calls[0].name == "get_standings"
    tool_messages = [m for m in create.call_args.kwargs["messages"] if isinstance(m, dict) and m.get("role") == "tool"]
    assert json.loads(tool_messages[0]["content"]) == rows
    assert create.call_args.kwargs["tool_choice"] == "none"


def test_real_madrid_id_is_resolved_and_model_id_ignored(db, monkeypatch):
    db.add_all([Team(id=41, external_id=86, name="Real Madrid CF"),
                Team(id=2, external_id=81, name="Other club")])
    db.flush()
    fetch = Mock(return_value=[])
    monkeypatch.setattr(module, "get_team_matches", fetch)
    args = module.parse_get_team_matches_args('{"team_id": 2, "limit": 5}')
    assert "team_id" not in args
    assert module.execute_get_team_matches(db, args) == []
    fetch.assert_called_once_with(db, 41, limit=5, status=None)


def test_missing_madrid_returns_empty_without_querying_other_team(db, monkeypatch):
    fetch = Mock()
    monkeypatch.setattr(module, "get_team_matches", fetch)
    assert module.execute_get_team_matches(db, {}) == []
    fetch.assert_not_called()


@pytest.mark.parametrize("url", ["postgres://u:p@host/db", "postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"])
def test_psycopg_v3_is_preserved(url):
    assert normalize_database_url(url) == "postgresql+psycopg://u:p@host/db"
