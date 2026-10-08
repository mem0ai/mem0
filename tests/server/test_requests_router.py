import importlib
import inspect
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session


SERVER_ROOT = Path(__file__).resolve().parents[2] / "server"


def _load_requests_router(monkeypatch, request):
    class TestBase(DeclarativeBase):
        pass

    class FakeRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return lambda endpoint: endpoint

    fake_auth = types.ModuleType("auth")
    fake_auth.require_admin = lambda: None
    fake_auth.verify_auth = lambda: None

    fake_db = types.ModuleType("db")
    fake_db.Base = TestBase
    fake_db.get_db = lambda: None

    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.APIRouter = FakeRouter
    fake_fastapi.Depends = lambda dependency=None, *args, **kwargs: dependency
    fake_fastapi.Query = lambda default=None, *args, **kwargs: default

    module_names = ("auth", "db", "fastapi", "models", "routers.requests")
    original_modules = {name: sys.modules.get(name) for name in module_names}

    def restore_modules():
        for name in module_names:
            sys.modules.pop(name, None)
            if original_modules[name] is not None:
                sys.modules[name] = original_modules[name]

    request.addfinalizer(restore_modules)

    monkeypatch.syspath_prepend(str(SERVER_ROOT))
    monkeypatch.setitem(sys.modules, "auth", fake_auth)
    monkeypatch.setitem(sys.modules, "db", fake_db)
    monkeypatch.setitem(sys.modules, "fastapi", fake_fastapi)
    monkeypatch.delitem(sys.modules, "models", raising=False)
    monkeypatch.delitem(sys.modules, "routers.requests", raising=False)
    return importlib.import_module("routers.requests"), TestBase, fake_auth.require_admin


def _build_db(requests_router, test_base):
    engine = create_engine("sqlite:///:memory:")
    test_base.metadata.create_all(engine)
    return engine


def _add_request_log(db, requests_router, *, path, auth_type, created_at):
    db.add(
        requests_router.RequestLog(
            method="GET",
            path=path,
            status_code=200,
            latency_ms=1,
            auth_type=auth_type,
            created_at=created_at,
        )
    )


def test_list_requests_returns_visible_auth_logs(monkeypatch, request):
    requests_router, test_base, _require_admin = _load_requests_router(monkeypatch, request)
    engine = _build_db(requests_router, test_base)
    now = datetime.now(timezone.utc)

    with Session(engine) as db:
        _add_request_log(db, requests_router, path="/none", auth_type="none", created_at=now + timedelta(seconds=5))
        _add_request_log(db, requests_router, path="/bearer", auth_type="bearer", created_at=now + timedelta(seconds=1))
        _add_request_log(db, requests_router, path="/api-key", auth_type="api_key", created_at=now + timedelta(seconds=2))
        _add_request_log(
            db, requests_router, path="/admin-key", auth_type="admin_api_key", created_at=now + timedelta(seconds=3)
        )
        _add_request_log(
            db, requests_router, path="/disabled", auth_type="disabled", created_at=now + timedelta(seconds=4)
        )
        db.commit()

        logs = requests_router.list_requests(_auth=object(), db=db, limit=10)

    assert [log.auth_type for log in logs] == ["disabled", "admin_api_key", "api_key", "bearer"]
    assert [log.path for log in logs] == ["/disabled", "/admin-key", "/api-key", "/bearer"]


def test_list_requests_applies_limit_after_filtering_visible_logs(monkeypatch, request):
    requests_router, test_base, _require_admin = _load_requests_router(monkeypatch, request)
    engine = _build_db(requests_router, test_base)
    now = datetime.now(timezone.utc)

    with Session(engine) as db:
        _add_request_log(db, requests_router, path="/none", auth_type="none", created_at=now + timedelta(seconds=5))
        _add_request_log(db, requests_router, path="/bearer", auth_type="bearer", created_at=now + timedelta(seconds=1))
        _add_request_log(db, requests_router, path="/api-key", auth_type="api_key", created_at=now + timedelta(seconds=2))
        _add_request_log(
            db, requests_router, path="/admin-key", auth_type="admin_api_key", created_at=now + timedelta(seconds=3)
        )
        _add_request_log(
            db, requests_router, path="/disabled", auth_type="disabled", created_at=now + timedelta(seconds=4)
        )
        db.commit()

        logs = requests_router.list_requests(_auth=object(), db=db, limit=2)

    assert [log.path for log in logs] == ["/disabled", "/admin-key"]


def test_list_requests_requires_admin_dependency(monkeypatch, request):
    requests_router, _test_base, require_admin = _load_requests_router(monkeypatch, request)

    signature = inspect.signature(requests_router.list_requests)

    assert signature.parameters["_auth"].default is require_admin
