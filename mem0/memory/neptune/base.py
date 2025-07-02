import logging
from abc import ABC, abstractmethod

from mem0.memory.utils import format_entities

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    raise ImportError("rank_bm25 is not installed. Please install it using pip install rank-bm25")

from mem0.graphs.tools import (
    DELETE_MEMORY_STRUCT_TOOL_GRAPH,
    DELETE_MEMORY_TOOL_GRAPH,
    EXTRACT_ENTITIES_STRUCT_TOOL,
    EXTRACT_ENTITIES_TOOL,
    RELATIONS_STRUCT_TOOL,
    RELATIONS_TOOL,
)
from mem0.graphs.utils import EXTRACT_RELATIONS_PROMPT, get_delete_messages
from mem0.utils.factory import EmbedderFactory, LlmFactory

logger = logging.getLogger(__name__)


class NeptuneBase(ABC):
    """
    Abstract base class for neptune (neptune analytics and neptune db) calls using OpenCypher
    to store/retrieve data
    """

    @staticmethod
    def _create_embedding_model(config):
        """
        :return: the Embedder model used for memory store
        """
        return EmbedderFactory.create(
            config.embedder.provider,
            config.embedder.config,
            {"enable_embeddings": True},
        )

    @staticmethod
    def _create_llm(config, llm_provider):
        """
        :return: the llm model used for memory store
        """
        return LlmFactory.create(llm_provider, config.llm.config)

    def add(self, data, filters):
        """
        Adds data to the graph.

        Args:
            data (str): The data to add to the graph.
            filters (dict): A dictionary containing filters to be applied during the addition.
        """
        entity_type_map = self._retrieve_nodes_from_data(data, filters)
        to_be_added = self._establish_nodes_relations_from_data(data, filters, entity_type_map)
        search_output = self._search_graph_db(node_list=list(entity_type_map.keys()), filters=filters)
        to_be_deleted = self._get_delete_entities_from_search_output(search_output, data, filters)

        deleted_entities = self._delete_entities(to_be_deleted, filters["user_id"])
        added_entities = self._add_entities(to_be_added, filters["user_id"], entity_type_map)

        return {"deleted_entities": deleted_entities, "added_entities": added_entities}

    def _retrieve_nodes_from_data(self, data, filters):
        """
        Extract all entities mentioned in the query.
        """
        _tools = [EXTRACT_ENTITIES_TOOL]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [EXTRACT_ENTITIES_STRUCT_TOOL]
        search_results = self.llm.generate_response(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a smart assistant who understands entities and their types in a given text. If user message contains self reference such as 'I', 'me', 'my' etc. then use {filters['user_id']} as the source entity. Extract all the entities from the text. ***DO NOT*** answer the question itself if the given text is a question.",
                },
                {"role": "user", "content": data},
            ],
            tools=_tools,
        )

        entity_type_map = {}

        try:
            for tool_call in search_results["tool_calls"]:
                if tool_call["name"] != "extract_entities":
                    continue
                for item in tool_call["arguments"]["entities"]:
                    entity_type_map[item["entity"]] = item["entity_type"]
        except Exception as e:
            logger.exception(
                f"Error in search tool: {e}, llm_provider={self.llm_provider}, search_results={search_results}"
            )

        entity_type_map = {k.lower().replace(" ", "_"): v.lower().replace(" ", "_") for k, v in entity_type_map.items()}
        return entity_type_map

    def _establish_nodes_relations_from_data(self, data, filters, entity_type_map):
        """
        Establish relations among the extracted nodes.
        """
        if self.config.graph_store.custom_prompt:
            messages = [
                {
                    "role": "system",
                    "content": EXTRACT_RELATIONS_PROMPT.replace("USER_ID", filters["user_id"]).replace(
                        "CUSTOM_PROMPT", f"4. {self.config.graph_store.custom_prompt}"
                    ),
                },
                {"role": "user", "content": data},
            ]
        else:
            messages = [
                {
                    "role": "system",
                    "content": EXTRACT_RELATIONS_PROMPT.replace("USER_ID", filters["user_id"]),
                },
                {
                    "role": "user",
                    "content": f"List of entities: {list(entity_type_map.keys())}. \n\nText: {data}",
                },
            ]

        _tools = [RELATIONS_TOOL]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [RELATIONS_STRUCT_TOOL]

        extracted_entities = self.llm.generate_response(
            messages=messages,
            tools=_tools,
        )

        entities = []
        if extracted_entities["tool_calls"]:
            entities = extracted_entities["tool_calls"][0]["arguments"]["entities"]

        entities = self._remove_spaces_from_entities(entities)
        logger.debug(f"Extracted entities: {entities}")
        return entities

    def _remove_spaces_from_entities(self, entity_list):
        for item in entity_list:
            item["source"] = item["source"].lower().replace(" ", "_")
            item["relationship"] = item["relationship"].lower().replace(" ", "_")
            item["destination"] = item["destination"].lower().replace(" ", "_")
        return entity_list

    def _get_delete_entities_from_search_output(self, search_output, data, filters):
        """
        Get the entities to be deleted from the search output.
        """

        search_output_string = format_entities(search_output)
        system_prompt, user_prompt = get_delete_messages(search_output_string, data, filters["user_id"])

        _tools = [DELETE_MEMORY_TOOL_GRAPH]
        if self.llm_provider in ["azure_openai_structured", "openai_structured"]:
            _tools = [
                DELETE_MEMORY_STRUCT_TOOL_GRAPH,
            ]

        memory_updates = self.llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=_tools,
        )

        to_be_deleted = []
        for item in memory_updates["tool_calls"]:
            if item["name"] == "delete_graph_memory":
                to_be_deleted.append(item["arguments"])
        # in case if it is not in the correct format
        to_be_deleted = self._remove_spaces_from_entities(to_be_deleted)
        logger.debug(f"Deleted relationships: {to_be_deleted}")
        return to_be_deleted

    def _delete_entities(self, to_be_deleted, user_id):
        """
        Delete the entities from the graph.
        """

        results = []
        for item in to_be_deleted:
            source = item["source"]
            destination = item["destination"]
            relationship = item["relationship"]

            # Delete the specific relationship between nodes
            cypher, params = self._delete_entities_cypher(source, destination, relationship, user_id)
            result = self.graph.query(cypher, params=params)
            results.append(result)
        return results

    @abstractmethod
    def _delete_entities_cypher(self, source, destination, relationship, user_id):
        """
        Returns the OpenCypher query and parameters for deleting entities in the graph DB
        """

        pass

    def _add_entities(self, to_be_added, user_id, entity_type_map):
        """
        Add the new entities to the graph. Merge the nodes if they already exist.
        """

        results = []
        for item in to_be_added:
            # entities
            source = item["source"]
            destination = item["destination"]
            relationship = item["relationship"]

            # types
            source_type = entity_type_map.get(source, "__User__")
            destination_type = entity_type_map.get(destination, "__User__")

            # embeddings
            source_embedding = self.embedding_model.embed(source)
            dest_embedding = self.embedding_model.embed(destination)

            # search for the nodes with the closest embeddings
            source_node_search_result = self._search_source_node(source_embedding, user_id, threshold=0.9)
            destination_node_search_result = self._search_destination_node(dest_embedding, user_id, threshold=0.9)

            cypher, params = self._add_entities_cypher(
                source_node_search_result,
                source,
                source_embedding,
                source_type,
                destination_node_search_result,
                destination,
                dest_embedding,
                destination_type,
                relationship,
                user_id,
            )
            result = self.graph.query(cypher, params=params)
            results.append(result)
        return results

    @abstractmethod
    def _add_entities_cypher(
        self,
        source_node_list,
        source,
        source_embedding,
        source_type,
        destination_node_list,
        destination,
        dest_embedding,
        destination_type,
        relationship,
        user_id,
    ):
        """
        Returns the OpenCypher query and parameters for adding entities in the graph DB
        """
        pass

    def search(self, query, filters, limit=100):
        """
        Search for memories and related graph data.

        Args:
            query (str): Query to search for.
            filters (dict): A dictionary containing filters to be applied during the search.
            limit (int): The maximum number of nodes and relationships to retrieve. Defaults to 100.

        Returns:
            dict: A dictionary containing:
                - "contexts": List of search results from the base data store.
                - "entities": List of related graph data based on the query.
        """

        entity_type_map = self._retrieve_nodes_from_data(query, filters)
        search_output = self._search_graph_db(node_list=list(entity_type_map.keys()), filters=filters)

        if not search_output:
            return []

        search_outputs_sequence = [
            [item["source"], item["relationship"], item["destination"]] for item in search_output
        ]
        bm25 = BM25Okapi(search_outputs_sequence)

        tokenized_query = query.split(" ")
        reranked_results = bm25.get_top_n(tokenized_query, search_outputs_sequence, n=5)

        search_results = []
        for item in reranked_results:
            search_results.append({"source": item[0], "relationship": item[1], "destination": item[2]})

        return search_results

    def _search_source_node(self, source_embedding, user_id, threshold=0.9):
        cypher, params = self._search_source_node_cypher(source_embedding, user_id, threshold)
        result = self.graph.query(cypher, params=params)
        return result

    @abstractmethod
    def _search_source_node_cypher(self, source_embedding, user_id, threshold):
        """
        Returns the OpenCypher query and parameters to search for source nodes
        """
        pass

    def _search_destination_node(self, destination_embedding, user_id, threshold=0.9):
        cypher, params = self._search_destination_node_cypher(destination_embedding, user_id, threshold)
        result = self.graph.query(cypher, params=params)
        return result

    @abstractmethod
    def _search_destination_node_cypher(self, destination_embedding, user_id, threshold):
        """
        Returns the OpenCypher query and parameters to search for destination nodes
        """
        pass

    def delete_all(self, filters):
        cypher, params = self._delete_all_cypher(filters)
        self.graph.query(cypher, params=params)

    @abstractmethod
    def _delete_all_cypher(self, filters):
        """
        Returns the OpenCypher query and parameters to delete all edges/nodes in the memory store
        """
        pass

    def get_all(self, filters, limit=100):
        """
        Retrieves all nodes and relationships from the graph database based on filtering criteria.

        Args:
            filters (dict): A dictionary containing filters to be applied during the retrieval.
            limit (int): The maximum number of nodes and relationships to retrieve. Defaults to 100.
        Returns:
            list: A list of dictionaries, each containing:
                - 'contexts': The base data store response for each memory.
                - 'entities': A list of strings representing the nodes and relationships
        """

        # return all nodes and relationships
        query, params = self._get_all_cypher(filters, limit)
        results = self.graph.query(query, params=params)

        final_results = []
        for result in results:
            final_results.append(
                {
                    "source": result["source"],
                    "relationship": result["relationship"],
                    "target": result["target"],
                }
            )

        logger.debug(f"Retrieved {len(final_results)} relationships")

        return final_results

    @abstractmethod
    def _get_all_cypher(self, filters, limit):
        """
        Returns the OpenCypher query and parameters to get all edges/nodes in the memory store
        """
        pass

    def _search_graph_db(self, node_list, filters, limit=100):
        """
        Search similar nodes among and their respective incoming and outgoing relations.
        """
        result_relations = []

        for node in node_list:
            n_embedding = self.embedding_model.embed(node)
            cypher_query, params = self._search_graph_db_cypher(n_embedding, filters, limit)
            ans = self.graph.query(cypher_query, params=params)
            result_relations.extend(ans)

        return result_relations

    @abstractmethod
    def _search_graph_db_cypher(self, n_embedding, filters, limit):
        """
        Returns the OpenCypher query and parameters to search for similar nodes in the memory store
        """
        pass

    # Reset is not defined in base.py
    def reset(self):
        """
        Reset the graph by clearing all nodes and relationships.

        link: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/neptune-graph/client/reset_graph.html
        """

        logger.warning("Clearing graph...")
        graph_id = self.graph.graph_identifier
        self.graph.client.reset_graph(
            graphIdentifier=graph_id,
            skipSnapshot=True,
        )
        waiter = self.graph.client.get_waiter("graph_available")
        waiter.wait(graphIdentifier=graph_id, WaiterConfig={"Delay": 10, "MaxAttempts": 60})
