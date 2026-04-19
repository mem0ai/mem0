from app.config import Settings, get_settings
from app.database import get_db_session


def get_app_settings() -> Settings:
    return get_settings()


__all__ = ["get_app_settings", "get_db_session"]
