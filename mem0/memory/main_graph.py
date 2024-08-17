from langchain.docstore.document import Document
from py2neo import Graph
from langchain_openai import ChatOpenAI
from langchain_community.graphs import Neo4jGraph
from langchain_experimental.graph_transformers import LLMGraphTransformer
from pydantic import BaseModel, Field
from datetime import datetime
import json
from mem0.graphs.utils import get_search_results
from openai import OpenAI

import numpy as np
from mem0.embeddings.openai import OpenAIEmbedding
from mem0.llms.openai import OpenAILLM
from mem0.graphs.utils import get_update_memory_messages, UPDATE_MEMORY_TOOL_GRAPH, ADD_MEMORY_TOOL_GRAPH

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
        self.pyneo_graph = Graph(self.config.graph_store.config.url, auth=(self.config.graph_store.config.username, self.config.graph_store.config.password))
        self.graph = Neo4jGraph(self.config.graph_store.config.url, self.config.graph_store.config.username, self.config.graph_store.config.password)
        self.llm_graph_transformer = LLMGraphTransformer(llm=ChatOpenAI(temperature=0, model_name="gpt-4o-mini"))

        # delete all nodes and relationships
        cypher = """
        MATCH (n)
        DETACH DELETE n
        """
        
        self.graph.query(cypher)

        self.llm = OpenAILLM()
        self.embedding_model = OpenAIEmbedding()

    def _add(self, message):

        search_output = self._search(message)
        print("search_output -----------------")
        for item in search_output:
            print(item['source'], item['relation'], item['destination'])
        print("search_output -----------------")
        
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": "You are a smart assistant who understands the entities, their types, and relations in a given text. Extract the entities, their types, and relations from the text. The realtionships should be atomic. If user message contains self reference such as 'I', 'me', 'my' etc. then use prateek as the source node."},
                {"role": "user", "content": message},
            ],
            response_format=ADDQuery,
        )

        output = completion.choices[0].message
        output = output.parsed.entities
        print("output -----------------", output)

        new_entities = []
        print("output -----------------")
        for item in output:
            new_entities.append(item)
        print("output -----------------")


        messages = get_update_memory_messages(search_output, output)
        tools = [UPDATE_MEMORY_TOOL_GRAPH, ADD_MEMORY_TOOL_GRAPH]

        response = self.llm.generate_response(messages=messages, tools=tools)

        print("response -----------------", response)

        to_be_added = []
        for item in response['tool_calls']:
            if item['name'] == "add_graph_memory":
                to_be_added.append(item['arguments'])
            elif item['name'] == "update_graph_memory":
                self._update_relationship(item['arguments']['source'], item['arguments']['destination'], item['arguments']['relationship'])

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

            print("New added nodes and relationship:")
            for record in result:
                print(f"Source: {record['n']['name']}, Destination: {record['m']['name']}")


    def _search(self, query):
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": "You are a smart assistant who understands the entities, their types, and relations in a given text. If user message contains self reference such as 'I', 'me', 'my' etc. then use prateek as the source node. Extract the entities."},
                {"role": "user", "content": query},
            ],
            response_format=SEARCHQuery,
        )

        output = completion.choices[0].message
        node_list = output.parsed.nodes
        relation_list = output.parsed.relations

        node_list = [node.lower().replace(" ", "_") for node in node_list]
        relation_list = [relation.lower().replace(" ", "_") for relation in relation_list]

        threshold = 0.7

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
            RETURN n.name AS source, id(n) AS source_id, type(r) AS relation, id(r) AS relation_id, m.name AS destination, id(m) AS destination_id, similarity
            UNION
            MATCH (n)
            WHERE n.embedding IS NOT NULL
            WITH n, 
                round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) / 
                (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) * 
                sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
            WHERE similarity >= $threshold
            MATCH (m)-[r]->(n)
            RETURN m.name AS source, id(m) AS source_id, type(r) AS relation, id(r) AS relation_id, n.name AS destination, id(n) AS destination_id, similarity
            ORDER BY similarity DESC
            """
            params = {"n_embedding": n_embedding, "threshold": threshold}
            ans = self.graph.query(cypher_query, params=params)
            result_relations.extend(ans)

        return result_relations


    def add(self, data, stored_memories):
        """
        Adds data to the graph.

        Args:
            data (str): The data to add to the graph.
            stored_memories (list): A list of stored memories.

        Returns:
            dict: A dictionary containing the entities added to the graph.
        """

        # data = "My name is prateek\n" + data
        # # Convert data to graph documents
        # query_doc = [Document(page_content=data)]
        # graph_documents = self.llm_graph_transformer.convert_to_graph_documents(query_doc)

        # print(graph_documents)



        # # Extract relationships from graph documents
        # new_relationships = []
        # for graph_doc in graph_documents:
        #     for relation in graph_doc.relationships:
        #         relationship_embedding = self.embedding_model.embed(relation.type)
                
        #         new_relationships.append(
        #             GraphData(
        #                 source=relation.source.id,
        #                 target=relation.target.id,
        #                 relationship=relation.type,
        #             )
        #         )
        #         # Add the embedding to the relationship properties
        #         relation.properties['embedding'] = relationship_embedding
        #         relation.properties['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        # Add graph documents to the graph
        # self.graph.add_graph_documents(
        #     graph_documents,
        #     baseEntityLabel=True,
        #     include_source=False
        # )

        self._add(data)
        new_relationships_response = []

        # new_relationships_response = [item.model_dump(include={"source", "target", "relationship"}) for item in new_relationships]

        # existing_relationships = []
        # for relationship in new_relationships:
        #     existing_relationships.extend(self._get_relationships(relationship.source, relationship.relationship))


        # if existing_relationships:
        #     serialized_existing_relationships = [
        #         item.model_dump(include={"source", "target", "relationship", "content"})
        #         for item in existing_relationships
        #     ]
        #     serialized_new_relationships = [
        #         item.model_dump(include={"source", "target", "relationship", "content"})
        #         for item in new_relationships
        #     ]

        #     messages = get_update_memory_messages(serialized_existing_relationships, serialized_new_relationships)
        #     tools = [UPDATE_MEMORY_TOOL_GRAPH]

        #     response = self.llm.generate_response(messages=messages, tools=tools)
        #     tool_calls = response['tool_calls']

        #     if tool_calls:
        #         for tool_call in tool_calls:
        #             function_args = tool_call['arguments']
        #             self._update_relationship(**function_args)             

        
        return {"entities": new_relationships_response}
    

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

        all_entities = self.get_all()
        results = json.loads(get_search_results(all_entities, query))

        return results['search_results']
    
    
    
    
    def _get_relationships(self, source_id, relationship_type, top_k=10, is_search=False):
        """
        Retrieves and ranks relationships based on similarity to a given relationship type.

        This method embeds the given relationship type, fetches all relationships with embeddings
        from the graph database, calculates similarities, and returns the top-k most similar relationships.

        Args:
            source_id (str): The ID of the source node.
            relationship_type (str): The type of relationship to compare against.
            top_k (int, optional): The number of top similar relationships to return. Defaults to 10.
            is_search (bool, optional): If True, returns a string representation of relationships.
                                        If False, returns GraphData objects. Defaults to False.

        Returns: 
            list: A list of GraphData objects or string representations of relationships.
        """
        relationship_embedding = self.embedding_model.embed(relationship_type)
        
        # Cypher query to fetch all relationships with embeddings
        query = """
        MATCH (source)-[r]->(target)
        WHERE r.embedding IS NOT NULL
        RETURN source, type(r) AS rel_type, target, r.embedding AS embedding, r.timestamp AS timestamp
        """
        results = self.graph.query(query)

        similarities = [
            (result['source'], result['rel_type'], result['target'], 
            self.cosine_similarity(relationship_embedding, result['embedding']), result['timestamp'])
            for result in results
        ]

        
        # Sort by similarity (descending) and get top_k results
        top_similar = sorted(similarities, key=lambda x: x[3], reverse=True)[:top_k]

        graph_data = []
        for result in top_similar:
            old_source_id = result[0]['id']
            old_target_id = result[2]['id']
            relationship = result[1]

            if is_search:
                record_str = f"{old_source_id} -> {relationship} -> {old_target_id}"
                graph_data.append(record_str)
            else:
                if source_id == old_source_id: 
                    graph_data.append(GraphData(
                        source=old_source_id,
                        target=old_target_id,
                        relationship=relationship,
                    ))
        
        return graph_data
    

    def get_all(self,):
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
        MATCH (n) -[r]-> (m)
        RETURN n.id, r, m.id
        """
        results = self.graph.query(query)

        final_results = []
        for result in results:
            final_results.append((result['n.id'], result['r'][1], result['m.id']))


        return final_results
    
    
    def _update_relationship(self, source, target, relationship):
        """
        Update the relationship between two nodes in the graph.

        Args:
            source (str): The name of the source node.
            target (str): The name of the target node.
            relationship (str): The new type of the relationship.

        Raises:
            Exception: If the nodes or relationship are not found in the graph.
        """
        # First, delete the existing relationship
        delete_query = """
        MATCH (n1 {name: $source})-[r]->(n2 {name: $target})
        DELETE r
        """
        self.graph.query(delete_query, params={"source": source, "target": target})

        # Then, create the new relationship
        create_query = f"""
        MATCH (n1 {{name: $source}}), (n2 {{name: $target}})
        CREATE (n1)-[r:{relationship}]->(n2)
        RETURN n1, r, n2
        """
        result = self.graph.query(create_query, params={"source": source, "target": target})

        if not result:
            raise Exception(f"Failed to update relationship between {source} and {target}")

    @staticmethod
    def cosine_similarity(a, b):
        """ Calculate the cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

