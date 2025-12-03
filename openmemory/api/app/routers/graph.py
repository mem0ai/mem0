import logging
import os
from typing import Any, Dict, List, Optional

from app.database import get_db
from app.models import User
from app.utils.permissions import check_memory_access_permissions
from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import GraphDatabase
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])

logger = logging.getLogger(__name__)


class GraphNode(BaseModel):
    """Represents a node in the graph."""
    id: str
    labels: List[str]
    properties: Dict[str, Any]


class GraphRelationship(BaseModel):
    """Represents a relationship in the graph."""
    id: str
    type: str
    source: str
    target: str
    properties: Dict[str, Any]


class GraphData(BaseModel):
    """Complete graph data with nodes and relationships."""
    nodes: List[GraphNode]
    relationships: List[GraphRelationship]


def get_neo4j_driver():
    """Get Neo4j driver instance."""
    url = os.environ.get('NEO4J_URL', 'neo4j://neo4j:7687')
    username = os.environ.get('NEO4J_USERNAME', 'neo4j')
    password = os.environ.get('NEO4J_PASSWORD')

    if not password:
        raise ValueError("NEO4J_PASSWORD environment variable is not set")

    return GraphDatabase.driver(url, auth=(username, password))


def neo4j_record_to_dict(record: Any) -> Dict[str, Any]:
    """Convert Neo4j record to dictionary."""
    result = {}
    for key in record.keys():
        value = record[key]
        if hasattr(value, '__dict__'):
            # Neo4j node or relationship
            result[key] = dict(value)
        else:
            result[key] = value
    return result


@router.get("/data", response_model=GraphData)
async def get_graph_data(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of nodes to return"),
    db: Session = Depends(get_db)
):
    """
    Get graph data from Neo4j for visualization.

    This endpoint retrieves nodes and relationships from the Neo4j graph database
    that stores memory entities and their connections created by mem0.

    If user_id is provided, only returns nodes related to that user's memories.
    """
    driver = None

    try:
        driver = get_neo4j_driver()

        with driver.session() as session:
            # Build Cypher query based on whether we're filtering by user
            if user_id:
                # Query nodes and relationships for a specific user
                query = """
                MATCH (n)
                WHERE n.user_id = $user_id
                WITH n LIMIT $limit
                MATCH (n)-[r]->(m)
                RETURN n, r, m
                """
                params = {"user_id": user_id, "limit": limit}
            else:
                # Query all nodes and relationships (limited)
                query = """
                MATCH (n)
                WITH n LIMIT $limit
                OPTIONAL MATCH (n)-[r]->(m)
                RETURN n, r, m
                """
                params = {"limit": limit}

            result = session.run(query, params)

            # Process results
            nodes_dict = {}  # Use dict to deduplicate nodes by ID
            relationships_list = []

            for record in result:
                # Process source node
                if record["n"]:
                    node = record["n"]
                    node_id = str(node.element_id)
                    if node_id not in nodes_dict:
                        # Get properties and exclude embedding arrays (too large)
                        props = dict(node)
                        props.pop('embedding', None)  # Remove embedding if present

                        nodes_dict[node_id] = GraphNode(
                            id=node_id,
                            labels=list(node.labels),
                            properties=props
                        )

                # Process relationship and target node
                if record["r"] and record["m"]:
                    rel = record["r"]
                    target_node = record["m"]

                    # Add target node
                    target_id = str(target_node.element_id)
                    if target_id not in nodes_dict:
                        # Get properties and exclude embedding arrays
                        target_props = dict(target_node)
                        target_props.pop('embedding', None)

                        nodes_dict[target_id] = GraphNode(
                            id=target_id,
                            labels=list(target_node.labels),
                            properties=target_props
                        )

                    # Add relationship
                    relationships_list.append(GraphRelationship(
                        id=str(rel.element_id),
                        type=rel.type,
                        source=node_id,
                        target=target_id,
                        properties=dict(rel)
                    ))

            return GraphData(
                nodes=list(nodes_dict.values()),
                relationships=relationships_list
            )

    except Exception as e:
        logger.error(f"Error fetching graph data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch graph data: {str(e)}")

    finally:
        if driver:
            driver.close()


@router.get("/stats")
async def get_graph_stats(
    user_id: Optional[str] = Query(None, description="Filter by user ID")
):
    """
    Get statistics about the graph.

    Returns counts of nodes, relationships, and node types.
    """
    driver = None

    try:
        driver = get_neo4j_driver()

        with driver.session() as session:
            if user_id:
                # Stats for specific user
                node_count_query = "MATCH (n) WHERE n.user_id = $user_id RETURN count(n) as count"
                rel_count_query = """
                MATCH (n)-[r]->(m)
                WHERE n.user_id = $user_id
                RETURN count(r) as count
                """
                label_count_query = """
                MATCH (n)
                WHERE n.user_id = $user_id
                RETURN labels(n)[0] as label, count(*) as count
                """
                params = {"user_id": user_id}
            else:
                # Stats for entire graph
                node_count_query = "MATCH (n) RETURN count(n) as count"
                rel_count_query = "MATCH ()-[r]->() RETURN count(r) as count"
                label_count_query = "MATCH (n) RETURN labels(n)[0] as label, count(*) as count"
                params = {}

            node_count = session.run(node_count_query, params).single()["count"]
            rel_count = session.run(rel_count_query, params).single()["count"]
            label_counts = [dict(record) for record in session.run(label_count_query, params)]

            return {
                "node_count": node_count,
                "relationship_count": rel_count,
                "node_types": label_counts
            }

    except Exception as e:
        logger.error(f"Error fetching graph stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch graph stats: {str(e)}")

    finally:
        if driver:
            driver.close()


@router.get("/search")
async def search_graph(
    query: str = Query(..., description="Search query for node properties"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=500)
):
    """
    Search for nodes in the graph by text search on properties.

    Searches across node properties and returns matching nodes with their immediate relationships.
    """
    driver = None

    try:
        driver = get_neo4j_driver()

        with driver.session() as session:
            if user_id:
                cypher_query = """
                MATCH (n)
                WHERE n.user_id = $user_id
                  AND any(prop in keys(n) WHERE toString(n[prop]) CONTAINS $query)
                WITH n LIMIT $limit
                OPTIONAL MATCH (n)-[r]-(m)
                RETURN n, r, m
                """
                params = {"query": query, "user_id": user_id, "limit": limit}
            else:
                cypher_query = """
                MATCH (n)
                WHERE any(prop in keys(n) WHERE toString(n[prop]) CONTAINS $query)
                WITH n LIMIT $limit
                OPTIONAL MATCH (n)-[r]-(m)
                RETURN n, r, m
                """
                params = {"query": query, "limit": limit}

            result = session.run(cypher_query, params)

            # Process results (similar to get_graph_data)
            nodes_dict = {}
            relationships_list = []

            for record in result:
                if record["n"]:
                    node = record["n"]
                    node_id = str(node.element_id)
                    if node_id not in nodes_dict:
                        props = dict(node)
                        props.pop('embedding', None)
                        nodes_dict[node_id] = GraphNode(
                            id=node_id,
                            labels=list(node.labels),
                            properties=props
                        )

                if record["r"] and record["m"]:
                    rel = record["r"]
                    target_node = record["m"]

                    target_id = str(target_node.element_id)
                    if target_id not in nodes_dict:
                        target_props = dict(target_node)
                        target_props.pop('embedding', None)
                        nodes_dict[target_id] = GraphNode(
                            id=target_id,
                            labels=list(target_node.labels),
                            properties=target_props
                        )

                    source_id = str(record["n"].element_id)
                    relationships_list.append(GraphRelationship(
                        id=str(rel.element_id),
                        type=rel.type,
                        source=source_id,
                        target=target_id,
                        properties=dict(rel)
                    ))

            return GraphData(
                nodes=list(nodes_dict.values()),
                relationships=relationships_list
            )

    except Exception as e:
        logger.error(f"Error searching graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search graph: {str(e)}")

    finally:
        if driver:
            driver.close()
