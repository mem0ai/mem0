
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def mock_alembic_command_upgrade():
    with mock.patch("alembic.command.upgrade"):
        yield
