"""
Utility functions for DynamoDB implementation in mem0.
"""

import json
from datetime import datetime, timezone

import boto3


def get_utc_timestamp() -> int:
    """
    Get current UTC timestamp in seconds.
    Uses the recommended timezone-aware approach instead of utcnow().

    Returns:
        timestamp: Current UTC timestamp in seconds
    """
    return int(datetime.now(timezone.utc).timestamp())


def create_dynamodb_tables(
    region: str,
    conversation_table_name: str,
    graph_table_name: str,
    ttl_enabled: bool = False,
    gsi_enabled: bool = True,
):
    """
    Create DynamoDB tables for mem0.

    Args:
        region: AWS region
        conversation_table_name: Name for the conversation table
        graph_table_name: Name for the graph table
        ttl_enabled: Whether to enable TTL for the conversation table
        gsi_enabled: Whether to enable GSI for the graph table

    Returns:
        success: True if tables were created successfully
    """
    dynamodb = boto3.client("dynamodb", region_name=region)

    # Create conversation table
    try:
        dynamodb.create_table(
            TableName=conversation_table_name,
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "conversation_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "conversation_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Wait for table to be created
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=conversation_table_name)

        # Enable TTL if requested
        if ttl_enabled:
            dynamodb.update_time_to_live(
                TableName=conversation_table_name,
                TimeToLiveSpecification={"Enabled": True, "AttributeName": "expiration_time"},
            )
    except Exception as e:
        print(f"Error creating conversation table: {e}")
        return False

    # Create graph table
    try:
        attribute_definitions = [
            {"AttributeName": "node_id", "AttributeType": "S"},
            {"AttributeName": "edge_id", "AttributeType": "S"},
        ]

        global_secondary_indexes = []

        if gsi_enabled:
            attribute_definitions.extend(
                [
                    {"AttributeName": "relationship_type", "AttributeType": "S"},
                    {"AttributeName": "created_at", "AttributeType": "N"},
                ]
            )

            global_secondary_indexes.append(
                {
                    "IndexName": "RelationshipTypeIndex",
                    "KeySchema": [
                        {"AttributeName": "relationship_type", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            )

        dynamodb.create_table(
            TableName=graph_table_name,
            KeySchema=[
                {"AttributeName": "node_id", "KeyType": "HASH"},
                {"AttributeName": "edge_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=attribute_definitions,
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=global_secondary_indexes if global_secondary_indexes else [],
        )

        # Wait for table to be created
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=graph_table_name)
    except Exception as e:
        print(f"Error creating graph table: {e}")
        return False

    return True


def generate_cloudformation_template(
    conversation_table_name: str, graph_table_name: str, ttl_enabled: bool = False, gsi_enabled: bool = True
) -> str:
    """
    Generate CloudFormation template for DynamoDB tables.

    Args:
        conversation_table_name: Name for the conversation table
        graph_table_name: Name for the graph table
        ttl_enabled: Whether to enable TTL for the conversation table
        gsi_enabled: Whether to enable GSI for the graph table

    Returns:
        template: CloudFormation template as a string
    """
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "DynamoDB tables for Mem0",
        "Resources": {
            "Mem0ConversationTable": {
                "Type": "AWS::DynamoDB::Table",
                "Properties": {
                    "TableName": conversation_table_name,
                    "BillingMode": "PAY_PER_REQUEST",
                    "AttributeDefinitions": [
                        {"AttributeName": "user_id", "AttributeType": "S"},
                        {"AttributeName": "conversation_id", "AttributeType": "S"},
                    ],
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "conversation_id", "KeyType": "RANGE"},
                    ],
                },
            },
            "Mem0GraphTable": {
                "Type": "AWS::DynamoDB::Table",
                "Properties": {
                    "TableName": graph_table_name,
                    "BillingMode": "PAY_PER_REQUEST",
                    "AttributeDefinitions": [
                        {"AttributeName": "node_id", "AttributeType": "S"},
                        {"AttributeName": "edge_id", "AttributeType": "S"},
                    ],
                    "KeySchema": [
                        {"AttributeName": "node_id", "KeyType": "HASH"},
                        {"AttributeName": "edge_id", "KeyType": "RANGE"},
                    ],
                },
            },
        },
    }

    # Add TTL if enabled
    if ttl_enabled:
        template["Resources"]["Mem0ConversationTable"]["Properties"]["TimeToLiveSpecification"] = {
            "AttributeName": "expiration_time",
            "Enabled": True,
        }

    # Add GSI if enabled
    if gsi_enabled:
        template["Resources"]["Mem0GraphTable"]["Properties"]["AttributeDefinitions"].extend(
            [
                {"AttributeName": "relationship_type", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "N"},
            ]
        )

        template["Resources"]["Mem0GraphTable"]["Properties"]["GlobalSecondaryIndexes"] = [
            {
                "IndexName": "RelationshipTypeIndex",
                "KeySchema": [
                    {"AttributeName": "relationship_type", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ]

    return json.dumps(template, indent=2)
