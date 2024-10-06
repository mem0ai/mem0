from typing import Optional
from pydantic import BaseModel, model_validator


class SqliteConfig(BaseModel):
    try:
        from sqlite3 import Connection
    except ImportError:
        raise ImportError(
            "The 'sqlite' library is required. "
            "Please install it using 'pip install sqlite'."
        )
    conn: Optional[Connection] = None
    db_path: Optional[str] = None

    @model_validator(mode='before')
    def check_config(cls, values):
        conn = values.get('conn')
        db_path = values.get('db_path')
    
        if not conn and not db_path:
            raise ValueError(
                "Either 'conn' or 'db_path' must be provided."
            )
        return values
