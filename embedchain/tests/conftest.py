import os

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(autouse=True)
def clean_db():
    db_path = os.path.expanduser("~/.embedchain/embedchain.db")
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    metadata = MetaData()
    metadata.reflect(bind=engine)  # Reflect schema from the engine
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Iterate over all tables in reversed order to respect foreign keys
        for table in reversed(metadata.sorted_tables):
            if table.name != "alembic_version":  # Skip the Alembic version table
                session.execute(table.delete())
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error cleaning database: {e}")
    finally:
        session.close()


@pytest.fixture(autouse=True)
def disable_telemetry():
    os.environ["EC_TELEMETRY"] = "false"
    yield
    del os.environ["EC_TELEMETRY"]