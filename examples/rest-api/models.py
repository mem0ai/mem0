from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Integer
from database import Base


class SetEnvKeys(BaseModel):
    keys: dict = Field({}, description="The keys that you want to set in the environment.")


class QueryApp(BaseModel):
    query: str = Field("", description="The query that you want to ask the App.")


class SourceApp(BaseModel):
    source: str = Field("", description="The source that you want to add to the App.")
    data_type: Optional[str] = Field("", description="The type of data to add, remove it for autosense.")


class DeployAppRequest(BaseModel):
    api_key: str = Field("", description="The Embedchain API key for App deployments.")


class MessageApp(BaseModel):
    message: str = Field("", description="The message that you want to send to the App.")


class ErrorResponse(BaseModel):
    error: str


class DefaultResponse(BaseModel):
    response: str


class AppModel(Base):
    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String, unique=True, index=True)
    config = Column(String, unique=True, index=True)
