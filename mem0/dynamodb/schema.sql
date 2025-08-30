-- DynamoDB Shell commands to create tables for mem0 DynamoDB implementation
-- These commands create the necessary tables and GSIs for storing conversation history and graph data
-- Mode information about DynamoDB Shell at https://github.com/awslabs/dynamodb-shell

-- Create the conversation history table
DROP TABLE IF EXISTS "Mem0Conversations";

CREATE TABLE "Mem0Conversations" (
    "user_id" string,
    "conversation_id" string
)
PRIMARY KEY ("user_id" HASH, "conversation_id" RANGE)
BILLING MODE ON DEMAND;

-- Enable TTL on the conversation table
ALTER TABLE "Mem0Conversations" SET TTL ("expiration_time");

-- Create the graph database table
DROP TABLE IF EXISTS "Mem0Graph";

CREATE TABLE "Mem0Graph" (
    "node_id" string,
    "edge_id" string,
    "relationship_type" string,
    "created_at" number
)
PRIMARY KEY ("node_id" HASH, "edge_id" RANGE)
BILLING MODE ON DEMAND
GSI ( "RelationshipTypeIndex"
    ON ("relationship_type" HASH, "created_at" RANGE)
    PROJECTING ALL
    BILLING MODE ON DEMAND
);

