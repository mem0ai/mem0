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
