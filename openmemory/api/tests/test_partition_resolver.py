"""Tests for the PartitionResolver (task_03 / ADR-002 / ADR-003).

Runs against in-memory SQLite with the real ORM models; no Qdrant required.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    MigrationState,
    MigrationStatus,
    PartitionTier,
    Project,
)
from app.utils.partitioning import CollectionRoute, PartitionResolver


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


def _resolver(factory):
    return PartitionResolver(session_factory=factory, default_collection="openmemory")


def test_fallback_when_no_migration_state(factory):
    resolver = _resolver(factory)
    assert resolver.active_collection() == "openmemory"
    route = resolver.route_for("any-project")
    assert route == CollectionRoute(collection="openmemory", shard_key=None)


def test_active_collection_from_migration_state(factory):
    db = factory()
    db.add(
        MigrationState(
            source_collection="openmemory",
            target_collection="openmemory_v2",
            active_collection="openmemory_v2",
            status=MigrationStatus.flipped,
        )
    )
    db.commit()
    db.close()

    resolver = _resolver(factory)
    assert resolver.active_collection() == "openmemory_v2"


def test_shared_project_has_no_shard_key(factory):
    db = factory()
    db.add(Project(name="small"))
    db.add(
        MigrationState(
            source_collection="blue",
            target_collection="green",
            active_collection="blue",
        )
    )
    db.commit()
    db.close()

    route = _resolver(factory).route_for("small")
    assert route.collection == "blue"
    assert route.shard_key is None


def test_dedicated_project_routes_to_shard_key(factory):
    db = factory()
    db.add(
        Project(name="big", partition_tier=PartitionTier.dedicated, shard_key="big")
    )
    db.add(
        MigrationState(
            source_collection="blue",
            target_collection="blue",
            active_collection="blue",
        )
    )
    db.commit()
    db.close()

    route = _resolver(factory).route_for("big")
    assert route.collection == "blue"
    assert route.shard_key == "big"


def test_cache_is_held_until_invalidate(factory):
    db = factory()
    state = MigrationState(
        source_collection="blue",
        target_collection="green",
        active_collection="blue",
    )
    db.add(state)
    db.commit()
    state_id = state.id
    db.close()

    resolver = _resolver(factory)
    assert resolver.active_collection() == "blue"  # caches snapshot

    # Flip the pointer directly in the DB.
    db = factory()
    db.query(MigrationState).filter_by(id=state_id).update(
        {"active_collection": "green"}
    )
    db.commit()
    db.close()

    # Still cached: returns the old value until invalidation.
    assert resolver.active_collection() == "blue"

    resolver.invalidate()
    assert resolver.active_collection() == "green"
