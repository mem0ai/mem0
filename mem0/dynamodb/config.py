"""
Configuration classes for DynamoDB-based storage in mem0.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class DynamoDBConfig(BaseModel):
    """Configuration for DynamoDB-based storage."""
    
    region: str = Field(default="us-east-1", description="AWS region for DynamoDB")
    table_name: str = Field(..., description="DynamoDB table name")
    endpoint_url: Optional[str] = Field(None, description="Custom endpoint URL for local testing")
    aws_access_key_id: Optional[str] = Field(None, description="AWS access key ID")
    aws_secret_access_key: Optional[str] = Field(None, description="AWS secret access key")
    use_iam_role: bool = Field(default=True, description="Use IAM role for authentication")
    
class DynamoDBConversationConfig(DynamoDBConfig):
    """Configuration for DynamoDB conversation store."""
    
    ttl_enabled: bool = Field(default=False, description="Enable TTL for conversations")
    ttl_attribute: str = Field(default="expiration_time", description="TTL attribute name")
    ttl_days: int = Field(default=30, description="Number of days until conversation expiration")
    
class DynamoDBGraphConfig(DynamoDBConfig):
    """Configuration for DynamoDB graph store."""
    
    enable_gsi: bool = Field(default=True, description="Enable GSI for efficient graph queries")
    gsi_name: str = Field(default="RelationshipTypeIndex", description="GSI name for relationship queries")
