from langchain_community.graphs import Neo4jGraph
from pydantic import BaseModel, Field
import json
from openai import OpenAI

from mem0.embeddings.openai import OpenAIEmbedding
from mem0.llms.openai import OpenAILLM
from mem0.graphs.utils import get_update_memory_messages, EXTRACT_ENTITIES_PROMPT
from mem0.graphs.tools import UPDATE_MEMORY_TOOL_GRAPH, ADD_MEMORY_TOOL_GRAPH, NOOP_TOOL

client = OpenAI()

class GraphData(BaseModel):
    source: str = Field(..., description="The source node of the relationship")
    target: str = Field(..., description="The target node of the relationship")
    relationship: str = Field(..., description="The type of the relationship")

class Entities(BaseModel):
    source_node: str
    source_type: str
    relation: str
    destination_node: str
    destination_type: str

class ADDQuery(BaseModel):
    entities: list[Entities]

class SEARCHQuery(BaseModel):
    nodes: list[str]
    relations: list[str]

def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

class MemoryGraph:
    def __init__(self, config):
        self.config = config
        self.graph = Neo4jGraph(self.config.graph_store.config.url, self.config.graph_store.config.username, self.config.graph_store.config.password)

        self.llm = OpenAILLM()
        self.embedding_model = OpenAIEmbedding()
        self.user_id = None
        self.threshold = 0.7
        self.model_name = "gpt-4o-2024-08-06"

    def add(self, data):
        """
        Adds data to the graph.

        Args:
            data (str): The data to add to the graph.
            stored_memories (list): A list of stored memories.

        Returns:
            dict: A dictionary containing the entities added to the graph.
        """
        
        # retrieve the search results
        search_output = self._search(data)
        
        extracted_entities = client.beta.chat.completions.parse(
            model=self.model_name,
            messages=[
                {"role": "system", "content": EXTRACT_ENTITIES_PROMPT.replace("USER_ID", self.user_id)},
                {"role": "user", "content": data},
            ],
            response_format=ADDQuery,
            temperature=0,
        ).choices[0].message.parsed.entities

        update_memory_prompt = get_update_memory_messages(search_output, extracted_entities)
        tools = [UPDATE_MEMORY_TOOL_GRAPH, ADD_MEMORY_TOOL_GRAPH, NOOP_TOOL]

        memory_updates = client.beta.chat.completions.parse(
            model=self.model_name,
            messages=update_memory_prompt,
            tools=tools,
            temperature=0,
        ).choices[0].message.tool_calls

        to_be_added = []
        for item in memory_updates:
            function_name = item.function.name
            arguments = json.loads(item.function.arguments)
            if function_name == "add_graph_memory":
                to_be_added.append(arguments)
            elif function_name == "update_graph_memory":
                self._update_relationship(arguments['source'], arguments['destination'], arguments['relationship'])
            elif function_name == "update_name":
                self._update_name(arguments['name'])
            elif function_name == "noop":
                continue

        new_relationships_response = []
        for item in to_be_added:
            source = item['source'].lower().replace(" ", "_")
            source_type = item['source_type'].lower().replace(" ", "_")
            relation = item['relationship'].lower().replace(" ", "_")
            destination = item['destination'].lower().replace(" ", "_")
            destination_type = item['destination_type'].lower().replace(" ", "_")

            # Create embeddings
            source_embedding = get_embedding(source)
            dest_embedding = get_embedding(destination)

            # Updated Cypher query to include node types and embeddings
            cypher = f"""
            MERGE (n:{source_type} {{name: $source_name}})
            ON CREATE SET n.created = timestamp(), n.embedding = $source_embedding
            ON MATCH SET n.embedding = $source_embedding
            MERGE (m:{destination_type} {{name: $dest_name}})
            ON CREATE SET m.created = timestamp(), m.embedding = $dest_embedding
            ON MATCH SET m.embedding = $dest_embedding
            MERGE (n)-[rel:{relation}]->(m)
            ON CREATE SET rel.created = timestamp()
            RETURN n, rel, m
            """

            params = {
                "source_name": source,
                "dest_name": destination,
                "source_embedding": source_embedding,
                "dest_embedding": dest_embedding
            }

            result = self.graph.query(cypher, params=params)



    def _search(self, query):
        search_results = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": f"You are a smart assistant who understands the entities, their types, and relations in a given text. If user message contains self reference such as 'I', 'me', 'my' etc. then use {self.user_id} as the source node. Extract the entities."},
                {"role": "user", "content": query},
            ],
            response_format=SEARCHQuery,
        ).choices[0].message
        
        node_list = search_results.parsed.nodes
        relation_list = search_results.parsed.relations

        node_list = [node.lower().replace(" ", "_") for node in node_list]
        relation_list = [relation.lower().replace(" ", "_") for relation in relation_list]

        result_relations = []

        for node in node_list:
            n_embedding = get_embedding(node)

            cypher_query = """
            MATCH (n)
            WHERE n.embedding IS NOT NULL
            WITH n, 
                round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) / 
                (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) * 
                sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
            WHERE similarity >= $threshold
            MATCH (n)-[r]->(m)
            RETURN n.name AS source, elementId(n) AS source_id, type(r) AS relation, elementId(r) AS relation_id, m.name AS destination, elementId(m) AS destination_id, similarity
            UNION
            MATCH (n)
            WHERE n.embedding IS NOT NULL
            WITH n, 
                round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) / 
                (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) * 
                sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
            WHERE similarity >= $threshold
            MATCH (m)-[r]->(n)
            RETURN m.name AS source, elementId(m) AS source_id, type(r) AS relation, elementId(r) AS relation_id, n.name AS destination, elementId(n) AS destination_id, similarity
            ORDER BY similarity DESC
            """
            params = {"n_embedding": n_embedding, "threshold": self.threshold}
            ans = self.graph.query(cypher_query, params=params)
            result_relations.extend(ans)

        return result_relations
    

    def search(self, query):
        """
        Search for memories and related graph data.

        Args:
            query (str): Query to search for.

        Returns:
            dict: A dictionary containing:
                - "contexts": List of search results from the base data store.
                - "entities": List of related graph data based on the query.
        """

        search_output = self._search(query)
        search_results = []
        for item in search_output:
            search_results.append({
                "source": item['source'],
                "relation": item['relation'],
                "destination": item['destination']
            })

        return search_results


    def delete_all(self):
        cypher = """
        MATCH (n)
        DETACH DELETE n
        """
        self.graph.query(cypher)
    

    def get_all(self):
        """
        Retrieves all nodes and relationships from the graph database based on optional filtering criteria.

        Args:
            all_memories (list): A list of dictionaries, each containing:
        Returns:
            list: A list of dictionaries, each containing:
                - 'contexts': The base data store response for each memory.
                - 'entities': A list of strings representing the nodes and relationships
        """

        # return all nodes and relationships
        query = """
        MATCH (n)-[r]->(m)
        RETURN n.name AS source, type(r) AS relationship, m.name AS target
        """
        results = self.graph.query(query)

        final_results = []
        for result in results:
            final_results.append({
                "source": result['source'],
                "relationship": result['relationship'],
                "target": result['target']
            })

        return final_results
    
    
    def _update_relationship(self, source, target, relationship):
        """
        Update or create a relationship between two nodes in the graph.

        Args:
            source (str): The name of the source node.
            target (str): The name of the target node.
            relationship (str): The type of the relationship.

        Raises:
            Exception: If the operation fails.
        """
        relationship = relationship.lower().replace(" ", "_")

        # Check if nodes exist and create them if they don't
        check_and_create_query = """
        MERGE (n1 {name: $source})
        MERGE (n2 {name: $target})
        """
        self.graph.query(check_and_create_query, params={"source": source, "target": target})

        # Delete any existing relationship between the nodes
        delete_query = """
        MATCH (n1 {name: $source})-[r]->(n2 {name: $target})
        DELETE r
        """
        self.graph.query(delete_query, params={"source": source, "target": target})

        # Create the new relationship
        create_query = f"""
        MATCH (n1 {{name: $source}}), (n2 {{name: $target}})
        CREATE (n1)-[r:{relationship}]->(n2)
        RETURN n1, r, n2
        """
        result = self.graph.query(create_query, params={"source": source, "target": target})

        if not result:
            raise Exception(f"Failed to update or create relationship between {source} and {target}")
