"""Shared fixtures for synaptic memory tests."""

from __future__ import annotations

from pathlib import Path

import pytest_asyncio

from synaptic_memory.memory_db import MemoryMetricsDB
from synaptic_memory.synapse_db import SynapseDB
from synaptic_memory.system import SynapticMemorySystem


@pytest_asyncio.fixture
async def synapse_db(tmp_path: Path) -> SynapseDB:
    db = SynapseDB(tmp_path / "synapses.db")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def memory_db(tmp_path: Path) -> MemoryMetricsDB:
    db = MemoryMetricsDB(tmp_path / "metrics.db")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def system(tmp_path: Path) -> SynapticMemorySystem:
    sys = SynapticMemorySystem(db_dir=tmp_path / "data")
    await sys.connect()
    yield sys
    await sys.close()
