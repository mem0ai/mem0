"""
DynamoDB implementation for conversation history storage in mem0.
"""

import json
from typing import Any, Dict, List, Optional

import boto3

from mem0.dynamodb.utils import get_utc_timestamp


class DynamoDBConversationStore:
    """DynamoDB implementation for conversation history storage."""

    def __init__(self, config):
        """
        Initialize DynamoDB conversation store.

        Args:
            config: Configuration containing AWS region, table name, etc.
        """
        self.config = config
        self.table_name = config.table_name
        self.region = config.region

        # Initialize DynamoDB client
        kwargs = {"region_name": self.region}
        if config.endpoint_url:
            kwargs["endpoint_url"] = config.endpoint_url
        if not config.use_iam_role:
            if config.aws_access_key_id and config.aws_secret_access_key:
                kwargs["aws_access_key_id"] = config.aws_access_key_id
                kwargs["aws_secret_access_key"] = config.aws_secret_access_key

        self.dynamodb = boto3.resource("dynamodb", **kwargs)
        self.table = self.dynamodb.Table(self.table_name)

    def store_conversation(
        self, user_id: str, messages: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store conversation in DynamoDB.

        Args:
            user_id: User identifier
            messages: List of message dictionaries
            metadata: Optional metadata

        Returns:
            conversation_id: Unique identifier for the conversation
        """
        conversation_id = f"{user_id}:{int(get_utc_timestamp())}"
        timestamp = get_utc_timestamp()

        item = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "messages": json.dumps(messages),
            "timestamp": timestamp,
            "type": "conversation",
        }

        if metadata:
            item["metadata"] = json.dumps(metadata)

        # Add TTL if enabled
        if self.config.ttl_enabled:
            expiration_time = get_utc_timestamp() + (self.config.ttl_days * 86400)  # days to seconds
            item[self.config.ttl_attribute] = expiration_time

        self.table.put_item(Item=item)
        return conversation_id

    def get_conversation(self, user_id: str, conversation_id: str) -> Dict[str, Any]:
        """
        Retrieve conversation from DynamoDB.

        Args:
            user_id: User identifier
            conversation_id: Conversation identifier

        Returns:
            conversation: Dictionary containing conversation data
        """
        response = self.table.get_item(Key={"user_id": user_id, "conversation_id": conversation_id})

        if "Item" not in response:
            return None

        item = response["Item"]
        return {
            "user_id": item["user_id"],
            "conversation_id": item["conversation_id"],
            "messages": json.loads(item["messages"]),
            "timestamp": item["timestamp"],
            "metadata": json.loads(item.get("metadata", "{}")),
        }

    def get_conversations_for_user(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent conversations for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of conversations to return

        Returns:
            conversations: List of conversation dictionaries
        """
        response = self.table.query(
            KeyConditionExpression="user_id = :user_id",
            ExpressionAttributeValues={":user_id": user_id},
            Limit=limit,
            ScanIndexForward=False,  # Return in descending order (newest first)
        )

        conversations = []
        for item in response.get("Items", []):
            conversations.append(
                {
                    "user_id": item["user_id"],
                    "conversation_id": item["conversation_id"],
                    "messages": json.loads(item["messages"]),
                    "timestamp": item["timestamp"],
                    "metadata": json.loads(item.get("metadata", "{}")),
                }
            )

        return conversations

    def update_conversation(
        self,
        user_id: str,
        conversation_id: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update an existing conversation.

        Args:
            user_id: User identifier
            conversation_id: Conversation identifier
            messages: Updated list of message dictionaries
            metadata: Optional updated metadata

        Returns:
            success: True if update was successful
        """
        update_expression = "SET messages = :messages, updated_at = :updated_at"
        expression_values = {":messages": json.dumps(messages), ":updated_at": get_utc_timestamp()}

        if metadata:
            update_expression += ", metadata = :metadata"
            expression_values[":metadata"] = json.dumps(metadata)

        try:
            self.table.update_item(
                Key={"user_id": user_id, "conversation_id": conversation_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
            )
            return True
        except Exception as e:
            print(f"Error updating conversation: {e}")
            return False

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Delete a conversation.

        Args:
            user_id: User identifier
            conversation_id: Conversation identifier

        Returns:
            success: True if deletion was successful
        """
        try:
            self.table.delete_item(Key={"user_id": user_id, "conversation_id": conversation_id})
            return True
        except Exception as e:
            print(f"Error deleting conversation: {e}")
            return False
