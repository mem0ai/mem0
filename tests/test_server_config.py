import importlib
import os
import sys
import types
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import MagicMock, patch

from fastapi import APIRouter
from pydantic import BaseModel

_SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server")
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)


def _reloaded_module(name: str):
    module = importlib.import_module(name)
    return importlib.reload(module)


def _fake_main_modules():
    fake_db = types.ModuleType("db")
    fake_db.SessionLocal = MagicMock()

    fake_auth = types.ModuleType("auth")
    fake_auth.ADMIN_API_KEY = ""
    fake_auth.AUTH_DISABLED = True
    fake_auth.JWT_SECRET = ""

    async def _allow(*args, **kwargs):
        return None

    fake_auth.require_admin = _allow
    fake_auth.verify_auth = _allow

    fake_models = types.ModuleType("models")
    fake_models.RequestLog = type("RequestLog", (), {})
    fake_models.User = type("User", (), {})

    fake_schemas = types.ModuleType("schemas")

    class MessageResponse(BaseModel):
        message: str

    fake_schemas.MessageResponse = MessageResponse

    class _Limiter:
        def limit(self, *args, **kwargs):
            def _decorator(func):
                return func

            return _decorator

    fake_rate_limit = types.ModuleType("rate_limit")
    fake_rate_limit.limiter = _Limiter()

    fake_telemetry = types.ModuleType("telemetry")
    fake_telemetry.log_status = lambda: None

    fake_errors = types.ModuleType("errors")

    class UpstreamError(Exception):
        pass

    fake_errors.UpstreamError = UpstreamError
    fake_errors.install_request_id_logging = lambda: None
    fake_errors.new_request_id = lambda: "req-test"
    fake_errors.request_id_var = object()
    fake_errors.upstream_error = lambda exc: exc

    async def _upstream_error_handler(*args, **kwargs):
        return None

    fake_errors.upstream_error_handler = _upstream_error_handler

    fake_slowapi = types.ModuleType("slowapi")
    fake_slowapi._rate_limit_exceeded_handler = lambda *args, **kwargs: None
    fake_slowapi_errors = types.ModuleType("slowapi.errors")
    fake_slowapi_errors.RateLimitExceeded = type("RateLimitExceeded", (Exception,), {})

    fake_routers = types.ModuleType("routers")
    fake_routers.__path__ = []
    fake_router_modules = {}
    for name in ("api_keys", "auth", "entities", "requests"):
        module = types.ModuleType(f"routers.{name}")
        module.router = APIRouter()
        fake_router_modules[f"routers.{name}"] = module

    modules = {
        "auth": fake_auth,
        "db": fake_db,
        "errors": fake_errors,
        "models": fake_models,
        "rate_limit": fake_rate_limit,
        "routers": fake_routers,
        "schemas": fake_schemas,
        "slowapi": fake_slowapi,
        "slowapi.errors": fake_slowapi_errors,
        "telemetry": fake_telemetry,
    }
    modules.update(fake_router_modules)
    return modules


@contextmanager
def _patched_relevant_env(overrides=None):
    overrides = overrides or {}
    relevant = {
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_COLLECTION_NAME",
        "OPENAI_API_KEY",
        "HISTORY_DB_PATH",
        "MEM0_DEFAULT_LLM_MODEL",
        "MEM0_DEFAULT_EMBEDDER_MODEL",
    }
    with patch.dict(os.environ, {}, clear=False):
        for key in relevant:
            os.environ.pop(key, None)
        for key, value in overrides.items():
            os.environ[key] = value
        yield


@contextmanager
def _server_runtime(*, initial_overrides=None, env=None):
    stored_overrides = deepcopy(initial_overrides or {})

    def _load():
        return deepcopy(stored_overrides)

    def _save(overrides):
        stored_overrides.clear()
        stored_overrides.update(deepcopy(overrides))

    with (
        patch("mem0.Memory.from_config", return_value=MagicMock()),
        _patched_relevant_env(env),
        patch.dict(sys.modules, _fake_main_modules()),
    ):
        sys.modules.pop("server.main", None)
        server_state = _reloaded_module("server_state")
        with (
            patch.object(server_state, "_load_overrides", side_effect=_load),
            patch.object(server_state, "_save_overrides", side_effect=_save),
        ):
            server_main = _reloaded_module("server.main")
            yield server_main, stored_overrides


def test_startup_env_api_key_beats_persisted_override():
    with _server_runtime(
        initial_overrides={"llm": {"config": {"api_key": "db-bad-key"}}},
        env={"OPENAI_API_KEY": "env-good-key"},
    ) as (server_main, _):
        current_config = server_main.get_current_config()

    assert current_config["llm"]["config"]["api_key"] == "env-good-key"


def test_startup_persisted_without_env_beats_default():
    with _server_runtime(
        initial_overrides={"llm": {"config": {"api_key": "db-good-key"}}},
    ) as (server_main, _):
        current_config = server_main.get_current_config()

    assert current_config["llm"]["config"]["api_key"] == "db-good-key"


def test_update_preserves_env_owned_field():
    with _server_runtime(
        initial_overrides={"llm": {"config": {"api_key": "db-bad-key"}}},
        env={"OPENAI_API_KEY": "env-good-key"},
    ) as (server_main, stored_overrides):
        updated = server_main.update_config({"llm": {"config": {"api_key": "db-new-key"}}})

    assert updated["llm"]["config"]["api_key"] == "env-good-key"
    assert stored_overrides["llm"]["config"]["api_key"] == "db-new-key"


def test_update_non_env_owned_field():
    with _server_runtime(env={"OPENAI_API_KEY": "env-good-key"}) as (server_main, stored_overrides):
        updated = server_main.update_config({"llm": {"config": {"temperature": 0.7}}})

    assert updated["llm"]["config"]["api_key"] == "env-good-key"
    assert updated["llm"]["config"]["temperature"] == 0.7
    assert stored_overrides["llm"]["config"]["temperature"] == 0.7


def test_restart_after_env_removal():
    persisted_overrides = {"llm": {"config": {"api_key": "db-good-key"}}}

    with _server_runtime(
        initial_overrides=persisted_overrides,
        env={"OPENAI_API_KEY": "env-good-key"},
    ) as (server_main, _):
        with_env = server_main.get_current_config()

    with _server_runtime(initial_overrides=persisted_overrides) as (server_main, _):
        without_env = server_main.get_current_config()

    assert with_env["llm"]["config"]["api_key"] == "env-good-key"
    assert without_env["llm"]["config"]["api_key"] == "db-good-key"
