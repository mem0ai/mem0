import os

import pytest


def clean_db():
    db_path = os.path.expanduser("~/.embedchain/embedchain.db")
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def setup():
    clean_db()
    yield
    clean_db()


@pytest.fixture(autouse=True)
def disable_telemetry():
    os.environ["EC_TELEMETRY"] = "false"
    yield
    del os.environ["EC_TELEMETRY"]
