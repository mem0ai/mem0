from typing import Optional
from pydantic import BaseModel, Field

class FeedoConfig(BaseModel):
    usage_key: str = Field(..., description="Feedo Protocol usage key")
    did: str = Field(..., description="Decentralized identity (DID) for the agent")
    namespace: Optional[str] = Field(default="", description="Tenant isolation namespace (e.g., room_id or user_id)")
