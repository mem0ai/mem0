from typing import ClassVar, Optional, Union
from pydantic import BaseModel, model_validator


class MysqlConfig(BaseModel):
    try:
        from mysql.connector.pooling import PooledMySQLConnection
        from mysql.connector.abstracts import MySQLConnectionAbstract
    except ImportError:
        raise ImportError(
            "The 'mysql' library is required. "
            "Please install it using 'pip install mysql-connector-python'."
        )
    PooledMySQLConnection: ClassVar[type] = PooledMySQLConnection
    MySQLConnectionAbstract: ClassVar[type] = MySQLConnectionAbstract

    conn: Optional[Union[PooledMySQLConnection, MySQLConnectionAbstract]] = None
    url: Optional[str] = None
    host: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    port: Optional[int] = 3306

    @model_validator(mode='before')
    def check_config(cls, values):
        url = values.get('url')
        conn = values.get('conn')
        host, user, password, database = (
            values.get('host'), 
            values.get('user'),
            values.get('password'),
            values.get('database'),
        )
        if not conn and not url and not (host and user and password and database):
            raise ValueError(
                "Either 'conn' or 'url' or 'host', 'user', 'password' and 'database' must be provided."
            )
        return values
    
    model_config = {
        "arbitrary_types_allowed": True,
    }

    
        