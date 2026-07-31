"""Drift test: every documented v3 add/search/list param must be reachable from the Python CLI."""

import json
from pathlib import Path

import typer.main

from mem0_cli.app import app

REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_PATH = REPO_ROOT / "docs" / "openapi.json"

KNOWN_UNSURFACED: dict[tuple[str, str], str] = {}

ADD_MAPPING: dict[str, list[str]] = {
    "messages": ["messages", "file", "text"],
    "user_id": ["user_id"],
    "agent_id": ["agent_id"],
    "run_id": ["run_id"],
    "metadata": ["metadata"],
    "expiration_date": ["expires"],
    "custom_instructions": ["custom_instructions"],
    "custom_categories": ["custom_categories"],
    "infer": ["no_infer"],
}

SEARCH_MAPPING: dict[str, list[str]] = {
    "query": ["query"],
    "filters": ["filter_json", "user_id", "agent_id", "run_id"],
    "show_expired": ["show_expired"],
    "top_k": ["top_k"],
    "threshold": ["threshold"],
    "rerank": ["rerank"],
    "reference_date": ["reference_date"],
}

LIST_MAPPING: dict[str, list[str]] = {
    "filters": ["user_id", "agent_id", "run_id", "category", "after", "before"],
    "show_expired": ["show_expired"],
}


def _documented_fields(endpoint: str) -> set[str]:
    spec = json.loads(OPENAPI_PATH.read_text())
    schema = spec["paths"][endpoint]["post"]["requestBody"]["content"]["application/json"]["schema"]
    return set(schema["properties"])


def _cli_param_names(command_name: str) -> set[str]:
    click_app = typer.main.get_command(app)
    command = click_app.commands[command_name]
    return {param.name for param in command.params}


def _assert_all_reachable(endpoint: str, mapping: dict[str, list[str]], command_name: str) -> None:
    documented = _documented_fields(endpoint)
    reachable = _cli_param_names(command_name)
    for field in documented:
        if (endpoint, field) in KNOWN_UNSURFACED:
            continue
        candidates = mapping.get(field)
        assert candidates, (
            f"{endpoint}: documented field {field!r} has no mapping entry for command {command_name!r}"
        )
        assert any(candidate in reachable for candidate in candidates), (
            f"{endpoint}: documented field {field!r} not reachable via any of {candidates} on command {command_name!r}"
        )


class TestOptionParity:
    def test_add_covers_documented_fields(self):
        _assert_all_reachable("/v3/memories/add/", ADD_MAPPING, "add")

    def test_search_covers_documented_fields(self):
        _assert_all_reachable("/v3/memories/search/", SEARCH_MAPPING, "search")

    def test_list_covers_documented_fields(self):
        _assert_all_reachable("/v3/memories/", LIST_MAPPING, "list")
