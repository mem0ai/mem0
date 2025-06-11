from typing import Optional

from database import Base
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String


class QueryApp(BaseModel):
    query: str = Field("", description="The query that you want to ask the App.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "Who is Elon Musk?",
            }
        }
    }


class SourceApp(BaseModel):
    source: str = Field("", description="The source that you want to add to the App.")
    data_type: Optional[str] = Field("", description="The type of data to add, remove it for autosense.")

    model_config = {"json_schema_extra": {"example": {"source": "https://en.wikipedia.org/wiki/Elon_Musk"}}}


class DeployAppRequest(BaseModel):
    api_key: str = Field("", description="The Embedchain API key for App deployments.")

    model_config = {"json_schema_extra": {"example": {"api_key": "ec-xxx"}}}


class MessageApp(BaseModel):
    message: str = Field("", description="The message that you want to send to the App.")


class DefaultResponse(BaseModel):
    response: str


class AppModel(Base):
    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String, unique=True, index=True)
    config = Column(String, unique=True, index=True)
