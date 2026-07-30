"""The contract tests. Each one pins a rule that was learned by breaking it against
the live API -- if one of these fails, the client has regressed to v1 behavior."""

import json

import pytest

from mem0_agent.api import Api, ContractError, expiry_date, results_of
from mem0_agent.breaker import Breaker
from mem0_agent.config import filters as F
from mem0_agent.config.project_config import DURABLE_TYPES, TYPES


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status = status
        self._body = body if body is not None else {"results": []}

    def read(self):
        return json.dumps(self._body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Recorder:
    """Stands in for urlopen so we can inspect exactly what would go on the wire."""

    def __init__(self, status=200, body=None):
        self.calls = []
        self.status = status
        self.body = body

    def __call__(self, req, timeout=None):
        self.calls.append({
            "method": req.get_method(),
            "url": req.full_url,
            "body": json.loads(req.data.decode()) if req.data else None,
        })
        return FakeResponse(self.status, self.body)

    @property
    def last(self):
        return self.calls[-1]


def make_api(**kw):
    rec = Recorder(**kw.pop("recorder_kw", {}))
    api = Api("key", org_id="org_X", project_id="proj_Y", opener=rec,
              breaker=Breaker(None), **kw)
    return api, rec


# --- Rule 1: a scope OVERRIDE travels in the body, never as a query param.
#     Omitting it is normal: the API key is already bound to one (org, project). ---
def test_writes_send_the_override_in_the_body():
    api, rec = make_api()
    api.add([{"role": "user", "content": "hi"}], user_id="u", infer=True)
    assert rec.last["body"]["project_id"] == "proj_Y"
    assert rec.last["body"]["org_id"] == "org_X"
    assert "project_id=" not in rec.last["url"]


def test_reads_send_the_override_in_the_body():
    api, rec = make_api()
    api.get_all(F.all_in_scope("u", "app"))
    assert rec.last["body"]["project_id"] == "proj_Y"
    assert "project_id=" not in rec.last["url"]


def test_feedback_carries_the_override_when_one_is_configured():
    """Feedback 404s only when the memory lives in a project the key is not bound to and
    no override is sent -- not, as first assumed, on every unpinned call."""
    api, rec = make_api()
    api.feedback("mem-1", "POSITIVE", "referenced in session")
    assert rec.last["body"]["project_id"] == "proj_Y"
    assert rec.last["body"]["org_id"] == "org_X"


def test_unpinned_calls_send_no_scope_and_let_the_key_decide():
    """An API key is already bound to one (org, project) server-side, so the ids are an
    override, not a requirement. Verified live: add, get_all and feedback all return 200
    with nothing in the body."""
    api, rec = make_api()
    api.org_id = api.project_id = None
    api.add([{"role": "user", "content": "hi"}], user_id="u", infer=True)
    body = rec.last["body"]
    assert "project_id" not in body and "org_id" not in body

    api.get_all(F.all_in_scope("u", "app"))
    assert "project_id" not in rec.last["body"]

    api.feedback("mem-1", "POSITIVE")
    assert "project_id" not in rec.last["body"]


def test_override_travels_in_the_body_when_both_ids_are_set():
    api, rec = make_api()
    api.get_all(F.all_in_scope("u", "app"))
    assert rec.last["body"]["project_id"] == "proj_Y"
    assert rec.last["body"]["org_id"] == "org_X"
    assert "project_id=" not in rec.last["url"], "query params are silently ignored"


def test_half_an_override_is_no_override():
    """One id alone would be ignored by the backend; sending it would only mislead."""
    api, _ = make_api()
    api.org_id = None
    assert api._pin() == {}


def test_project_endpoints_resolve_scope_from_the_key():
    """Only the project-config endpoints need the ids, and they ask the API for them."""
    api, rec = make_api(recorder_kw={"body": {"org_id": "org_ping", "project_id": "proj_ping"}})
    api.org_id = api.project_id = None
    api.project_get(fields=["decay"])
    assert "/organizations/org_ping/projects/proj_ping/" in rec.last["url"]
    assert rec.calls[0]["url"].endswith("/v1/ping/"), "scope comes from ping, not from config"


# --- Rule 2: latest_only on every read, or superseded facts resurface ---
@pytest.mark.parametrize("method,args", [
    ("get_all", ({"AND": []},)),
    ("search", ("q", {"AND": []})),
])
def test_reads_default_to_latest_only(method, args):
    api, rec = make_api()
    getattr(api, method)(*args)
    assert rec.last["body"]["latest_only"] is True


def test_strict_mode_blocks_superseded_reads():
    api = Api("key", org_id="o", project_id="p", strict=True, opener=Recorder())
    with pytest.raises(ContractError):
        api.get_all({"AND": []}, latest_only=False)


def test_superseded_reads_allowed_when_explicitly_auditing():
    api = Api("key", org_id="o", project_id="p", strict=True, opener=Recorder(),
              breaker=Breaker(None))
    status, _ = api.get_all({"AND": []}, latest_only=False, _allow_superseded=True)
    assert status == 200


# --- Rule 3: metadata.type is the read-time taxonomy, categories are secondary ---
def test_type_filters_match_metadata_and_categories():
    f = F.context_pack("u", "app")
    blob = json.dumps(f)
    for t in DURABLE_TYPES:
        assert f'{{"metadata": {{"type": "{t}"}}}}' in blob.replace("'", '"')
    assert '"categories"' in blob


# --- Rule 4: NOT takes a list ---
def test_not_clauses_are_lists():
    for f in (F.user_prefs("u"), F.context_pack("u", "app")):
        for clause in json.dumps(f).split('"NOT": ')[1:]:
            assert clause.lstrip().startswith("["), "NOT must wrap a list; the object form 400s"


def test_user_scope_excludes_project_records():
    """Implicit null scoping does not work -- the NOT clause is what makes this correct."""
    f = F.user_prefs("u")
    assert {"NOT": [{"app_id": "*"}]} in f["AND"]


def test_context_pack_spans_both_scopes():
    f = F.context_pack("u", "app")
    scope = [c for c in f["AND"] if "OR" in c][0]["OR"]
    assert {"app_id": "app"} in scope
    assert {"NOT": [{"app_id": "*"}]} in scope


# --- entity rules ---
def test_no_run_id_or_agent_id_anywhere():
    """v1 wrote summaries with run_id that no read path could ever return."""
    blob = json.dumps([
        F.context_pack("u", "a"), F.user_prefs("u"), F.session_state("u", "a", "s"),
        F.error_assist("u", "a"), F.all_in_scope("u", "a"), F.by_session("u", "a", "s"),
    ])
    assert "run_id" not in blob and "agent_id" not in blob


def test_session_state_is_found_by_metadata():
    f = F.session_state("u", "app", "sess-1")
    assert {"metadata": {"type": "session_state"}} in f["AND"]
    assert {"metadata": {"session_id": "sess-1"}} in f["AND"]


# --- endpoint quirks ---
def test_delete_all_uses_query_params_not_a_body():
    api, rec = make_api()
    api.delete_all(user_id="u")
    assert rec.last["body"] is None
    assert "user_id=u" in rec.last["url"]


def test_project_fields_are_repeated_params():
    api, rec = make_api()
    api.project_get(fields=["custom_instructions", "decay"])
    assert "fields=custom_instructions&fields=decay" in rec.last["url"]
    assert "fields=custom_instructions%2C" not in rec.last["url"]


def test_get_all_paginates_via_query_params():
    api, rec = make_api()
    api.get_all({"AND": []}, page=2, page_size=30)
    assert "page=2" in rec.last["url"] and "page_size=30" in rec.last["url"]
    assert "filters" in rec.last["body"]


# --- resilience: hooks must never block a session ---
def test_network_errors_fail_open():
    def boom(req, timeout=None):
        raise OSError("connection reset")

    api = Api("key", org_id="o", project_id="p", opener=boom, breaker=Breaker(None))
    status, body = api.get_all({"AND": []})
    assert status == 0 and "error" in body


def test_breaker_opens_after_threshold_and_reports_once():
    clock = [1000.0]
    b = Breaker(None, threshold=3, cooldown=600, clock=lambda: clock[0])
    for _ in range(3):
        b.record_failure()
    assert b.is_open
    assert b.take_notice() is not None
    assert b.take_notice() is None, "the outage should be announced once, not every call"
    clock[0] += 601
    assert b.allow()


def test_client_side_errors_do_not_trip_the_breaker():
    """A 400 is our bug, not an outage -- tripping on it would disable memory needlessly."""
    import urllib.error

    def bad_request(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)

    b = Breaker(None)
    api = Api("key", org_id="o", project_id="p", opener=bad_request, breaker=b)
    api.get_all({"AND": []})
    assert b.allow()


def test_breaker_short_circuits_when_open():
    b = Breaker(None, threshold=1)
    b.record_failure()
    rec = Recorder()
    api = Api("key", org_id="o", project_id="p", opener=rec, breaker=b)
    status, _ = api.get_all({"AND": []})
    assert status == 0 and rec.calls == [], "no request should leave the machine while open"


# --- helpers ---
def test_results_of_handles_both_shapes():
    assert results_of({"results": [{"id": 1}]}) == [{"id": 1}]
    assert results_of([{"id": 2}]) == [{"id": 2}]
    assert results_of(None) == []


def test_expiry_date_format():
    assert expiry_date(14, now=0) == "1970-01-15"


def test_taxonomy_is_closed():
    assert set(DURABLE_TYPES) < set(TYPES)
    assert "session_state" in TYPES and "session_state" not in DURABLE_TYPES
    assert "auto_capture" not in TYPES, "v1's catch-all bucket must not come back"
