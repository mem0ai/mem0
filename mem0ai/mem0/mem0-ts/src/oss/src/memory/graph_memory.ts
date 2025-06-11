import neo4j, { Driver } from "neo4j-driver";
import { BM25 } from "../utils/bm25";
import { GraphStoreConfig } from "../graphs/configs";
import { MemoryConfig } from "../types";
import { EmbedderFactory, LLMFactory } from "../utils/factory";
import { Embedder } from "../embeddings/base";
import { LLM } from "../llms/base";
import {
  DELETE_MEMORY_TOOL_GRAPH,
  EXTRACT_ENTITIES_TOOL,
  RELATIONS_TOOL,
} from "../graphs/tools";
import { EXTRACT_RELATIONS_PROMPT, getDeleteMessages } from "../graphs/utils";
import { logger } from "../utils/logger";

interface SearchOutput {
  source: string;
  source_id: string;
  relationship: string;
  relation_id: string;
  destination: string;
  destination_id: string;
  similarity: number;
}

interface ToolCall {
  name: string;
  arguments: string;
}

interface LLMResponse {
  toolCalls?: ToolCall[];
}

interface Tool {
  type: string;
  function: {
    name: string;
    description: string;
    parameters: Record<string, any>;
  };
}

interface GraphMemoryResult {
  deleted_entities: any[];
  added_entities: any[];
  relations?: any[];
}

export class MemoryGraph {
  private config: MemoryConfig;
  private graph: Driver;
  private embeddingModel: Embedder;
  private llm: LLM;
  private structuredLlm: LLM;
  private llmProvider: string;
  private threshold: number;

  constructor(config: MemoryConfig) {
    this.config = config;
    if (
      !config.graphStore?.config?.url ||
      !config.graphStore?.config?.username ||
      !config.graphStore?.config?.password
    ) {
      throw new Error("Neo4j configuration is incomplete");
    }

    this.graph = neo4j.driver(
      config.graphStore.config.url,
      neo4j.auth.basic(
        config.graphStore.config.username,
        config.graphStore.config.password,
      ),
    );

    this.embeddingModel = EmbedderFactory.create(
      this.config.embedder.provider,
      this.config.embedder.config,
    );

    this.llmProvider = "openai";
    if (this.config.llm?.provider) {
      this.llmProvider = this.config.llm.provider;
    }
    if (this.config.graphStore?.llm?.provider) {
      this.llmProvider = this.config.graphStore.llm.provider;
    }

    this.llm = LLMFactory.create(this.llmProvider, this.config.llm.config);
    this.structuredLlm = LLMFactory.create(
      "openai_structured",
      this.config.llm.config,
    );
    this.threshold = 0.7;
  }

  async add(
    data: string,
    filters: Record<string, any>,
  ): Promise<GraphMemoryResult> {
    const entityTypeMap = await this._retrieveNodesFromData(data, filters);

    const toBeAdded = await this._establishNodesRelationsFromData(
      data,
      filters,
      entityTypeMap,
    );

    const searchOutput = await this._searchGraphDb(
      Object.keys(entityTypeMap),
      filters,
    );

    const toBeDeleted = await this._getDeleteEntitiesFromSearchOutput(
      searchOutput,
      data,
      filters,
    );

    const deletedEntities = await this._deleteEntities(
      toBeDeleted,
      filters["userId"],
    );

    const addedEntities = await this._addEntities(
      toBeAdded,
      filters["userId"],
      entityTypeMap,
    );

    return {
      deleted_entities: deletedEntities,
      added_entities: addedEntities,
      relations: toBeAdded,
    };
  }

  async search(query: string, filters: Record<string, any>, limit = 100) {
    const entityTypeMap = await this._retrieveNodesFromData(query, filters);
    const searchOutput = await this._searchGraphDb(
      Object.keys(entityTypeMap),
      filters,
    );

    if (!searchOutput.length) {
      return [];
    }

    const searchOutputsSequence = searchOutput.map((item) => [
      item.source,
      item.relationship,
      item.destination,
    ]);

    const bm25 = new BM25(searchOutputsSequence);
    const tokenizedQuery = query.split(" ");
    const rerankedResults = bm25.search(tokenizedQuery).slice(0, 5);

    const searchResults = rerankedResults.map((item) => ({
      source: item[0],
      relationship: item[1],
      destination: item[2],
    }));

    logger.info(`Returned ${searchResults.length} search results`);
    return searchResults;
  }

  async deleteAll(filters: Record<string, any>) {
    const session = this.graph.session();
    try {
      await session.run("MATCH (n {user_id: $user_id}) DETACH DELETE n", {
        user_id: filters["userId"],
      });
    } finally {
      await session.close();
    }
  }

  async getAll(filters: Record<string, any>, limit = 100) {
    const session = this.graph.session();
    try {
      const result = await session.run(
        `
        MATCH (n {user_id: $user_id})-[r]->(m {user_id: $user_id})
        RETURN n.name AS source, type(r) AS relationship, m.name AS target
        LIMIT toInteger($limit)
        `,
        { user_id: filters["userId"], limit: Math.floor(Number(limit)) },
      );

      const finalResults = result.records.map((record) => ({
        source: record.get("source"),
        relationship: record.get("relationship"),
        target: record.get("target"),
      }));

      logger.info(`Retrieved ${finalResults.length} relationships`);
      return finalResults;
    } finally {
      await session.close();
    }
  }

  private async _retrieveNodesFromData(
    data: string,
    filters: Record<string, any>,
  ) {
    const tools = [EXTRACT_ENTITIES_TOOL] as Tool[];
    const searchResults = await this.structuredLlm.generateResponse(
      [
        {
          role: "system",
          content: `You are a smart assistant who understands entities and their types in a given text. If user message contains self reference such as 'I', 'me', 'my' etc. then use ${filters["userId"]} as the source entity. Extract all the entities from the text. ***DO NOT*** answer the question itself if the given text is a question.`,
        },
        { role: "user", content: data },
      ],
      { type: "json_object" },
      tools,
    );

    let entityTypeMap: Record<string, string> = {};
    try {
      if (typeof searchResults !== "string" && searchResults.toolCalls) {
        for (const call of searchResults.toolCalls) {
          if (call.name === "extract_entities") {
            const args = JSON.parse(call.arguments);
            for (const item of args.entities) {
              entityTypeMap[item.entity] = item.entity_type;
            }
          }
        }
      }
    } catch (e) {
      logger.error(`Error in search tool: ${e}`);
    }

    entityTypeMap = Object.fromEntries(
      Object.entries(entityTypeMap).map(([k, v]) => [
        k.toLowerCase().replace(/ /g, "_"),
        v.toLowerCase().replace(/ /g, "_"),
      ]),
    );

    logger.debug(`Entity type map: ${JSON.stringify(entityTypeMap)}`);
    return entityTypeMap;
  }

  private async _establishNodesRelationsFromData(
    data: string,
    filters: Record<string, any>,
    entityTypeMap: Record<string, string>,
  ) {
    let messages;
    if (this.config.graphStore?.customPrompt) {
      messages = [
        {
          role: "system",
          content:
            EXTRACT_RELATIONS_PROMPT.replace(
              "USER_ID",
              filters["userId"],
            ).replace(
              "CUSTOM_PROMPT",
              `4. ${this.config.graphStore.customPrompt}`,
            ) + "\nPlease provide your response in JSON format.",
        },
        { role: "user", content: data },
      ];
    } else {
      messages = [
        {
          role: "system",
          content:
            EXTRACT_RELATIONS_PROMPT.replace("USER_ID", filters["userId"]) +
            "\nPlease provide your response in JSON format.",
        },
        {
          role: "user",
          content: `List of entities: ${Object.keys(entityTypeMap)}. \n\nText: ${data}`,
        },
      ];
    }

    const tools = [RELATIONS_TOOL] as Tool[];
    const extractedEntities = await this.structuredLlm.generateResponse(
      messages,
      { type: "json_object" },
      tools,
    );

    let entities: any[] = [];
    if (typeof extractedEntities !== "string" && extractedEntities.toolCalls) {
      const toolCall = extractedEntities.toolCalls[0];
      if (toolCall && toolCall.arguments) {
        const args = JSON.parse(toolCall.arguments);
        entities = args.entities || [];
      }
    }

    entities = this._removeSpacesFromEntities(entities);
    logger.debug(`Extracted entities: ${JSON.stringify(entities)}`);
    return entities;
  }

  private async _searchGraphDb(
    nodeList: string[],
    filters: Record<string, any>,
    limit = 100,
  ): Promise<SearchOutput[]> {
    const resultRelations: SearchOutput[] = [];
    const session = this.graph.session();

    try {
      for (const node of nodeList) {
        const nEmbedding = await this.embeddingModel.embed(node);

        const cypher = `
          MATCH (n)
          WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
          WITH n,
              round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) /
              (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) *
              sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
          WHERE similarity >= $threshold
          MATCH (n)-[r]->(m)
          RETURN n.name AS source, elementId(n) AS source_id, type(r) AS relationship, elementId(r) AS relation_id, m.name AS destination, elementId(m) AS destination_id, similarity
          UNION
          MATCH (n)
          WHERE n.embedding IS NOT NULL AND n.user_id = $user_id
          WITH n,
              round(reduce(dot = 0.0, i IN range(0, size(n.embedding)-1) | dot + n.embedding[i] * $n_embedding[i]) /
              (sqrt(reduce(l2 = 0.0, i IN range(0, size(n.embedding)-1) | l2 + n.embedding[i] * n.embedding[i])) *
              sqrt(reduce(l2 = 0.0, i IN range(0, size($n_embedding)-1) | l2 + $n_embedding[i] * $n_embedding[i]))), 4) AS similarity
          WHERE similarity >= $threshold
          MATCH (m)-[r]->(n)
          RETURN m.name AS source, elementId(m) AS source_id, type(r) AS relationship, elementId(r) AS relation_id, n.name AS destination, elementId(n) AS destination_id, similarity
          ORDER BY similarity DESC
          LIMIT toInteger($limit)
        `;

        const result = await session.run(cypher, {
          n_embedding: nEmbedding,
          threshold: this.threshold,
          user_id: filters["userId"],
          limit: Math.floor(Number(limit)),
        });

        resultRelations.push(
          ...result.records.map((record) => ({
            source: record.get("source"),
            source_id: record.get("source_id").toString(),
            relationship: record.get("relationship"),
            relation_id: record.get("relation_id").toString(),
            destination: record.get("destination"),
            destination_id: record.get("destination_id").toString(),
            similarity: record.get("similarity"),
          })),
        );
      }
    } finally {
      await session.close();
    }

    return resultRelations;
  }

  private async _getDeleteEntitiesFromSearchOutput(
    searchOutput: SearchOutput[],
    data: string,
    filters: Record<string, any>,
  ) {
    const searchOutputString = searchOutput
      .map(
        (item) =>
          `${item.source} -- ${item.relationship} -- ${item.destination}`,
      )
      .join("\n");

    const [systemPrompt, userPrompt] = getDeleteMessages(
      searchOutputString,
      data,
      filters["userId"],
    );

    const tools = [DELETE_MEMORY_TOOL_GRAPH] as Tool[];
    const memoryUpdates = await this.structuredLlm.generateResponse(
      [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
      { type: "json_object" },
      tools,
    );

    const toBeDeleted: any[] = [];
    if (typeof memoryUpdates !== "string" && memoryUpdates.toolCalls) {
      for (const item of memoryUpdates.toolCalls) {
        if (item.name === "delete_graph_memory") {
          toBeDeleted.push(JSON.parse(item.arguments));
        }
      }
    }

    const cleanedToBeDeleted = this._removeSpacesFromEntities(toBeDeleted);
    logger.debug(
      `Deleted relationships: ${JSON.stringify(cleanedToBeDeleted)}`,
    );
    return cleanedToBeDeleted;
  }

  private async _deleteEntities(toBeDeleted: any[], userId: string) {
    const results: any[] = [];
    const session = this.graph.session();

    try {
      for (const item of toBeDeleted) {
        const { source, destination, relationship } = item;

        const cypher = `
          MATCH (n {name: $source_name, user_id: $user_id})
          -[r:${relationship}]->
          (m {name: $dest_name, user_id: $user_id})
          DELETE r
          RETURN 
              n.name AS source,
              m.name AS target,
              type(r) AS relationship
        `;

        const result = await session.run(cypher, {
          source_name: source,
          dest_name: destination,
          user_id: userId,
        });

        results.push(result.records);
      }
    } finally {
      await session.close();
    }

    return results;
  }

  private async _addEntities(
    toBeAdded: any[],
    userId: string,
    entityTypeMap: Record<string, string>,
  ) {
    const results: any[] = [];
    const session = this.graph.session();

    try {
      for (const item of toBeAdded) {
        const { source, destination, relationship } = item;
        const sourceType = entityTypeMap[source] || "unknown";
        const destinationType = entityTypeMap[destination] || "unknown";

        const sourceEmbedding = await this.embeddingModel.embed(source);
        const destEmbedding = await this.embeddingModel.embed(destination);

        const sourceNodeSearchResult = await this._searchSourceNode(
          sourceEmbedding,
          userId,
        );
        const destinationNodeSearchResult = await this._searchDestinationNode(
          destEmbedding,
          userId,
        );

        let cypher: string;
        let params: Record<string, any>;

        if (
          destinationNodeSearchResult.length === 0 &&
          sourceNodeSearchResult.length > 0
        ) {
          cypher = `
            MATCH (source)
            WHERE elementId(source) = $source_id
            MERGE (destination:${destinationType} {name: $destination_name, user_id: $user_id})
            ON CREATE SET
                destination.created = timestamp(),
                destination.embedding = $destination_embedding
            MERGE (source)-[r:${relationship}]->(destination)
            ON CREATE SET 
                r.created = timestamp()
            RETURN source.name AS source, type(r) AS relationship, destination.name AS target
          `;

          params = {
            source_id: sourceNodeSearchResult[0].elementId,
            destination_name: destination,
            destination_embedding: destEmbedding,
            user_id: userId,
          };
        } else if (
          destinationNodeSearchResult.length > 0 &&
          sourceNodeSearchResult.length === 0
        ) {
          cypher = `
            MATCH (destination)
            WHERE elementId(destination) = $destination_id
            MERGE (source:${sourceType} {name: $source_name, user_id: $user_id})
            ON CREATE SET
                source.created = timestamp(),
                source.embedding = $source_embedding
            MERGE (source)-[r:${relationship}]->(destination)
            ON CREATE SET 
                r.created = timestamp()
            RETURN source.name AS source, type(r) AS relationship, destination.name AS target
          `;

          params = {
            destination_id: destinationNodeSearchResult[0].elementId,
            source_name: source,
            source_embedding: sourceEmbedding,
            user_id: userId,
          };
        } else if (
          sourceNodeSearchResult.length > 0 &&
          destinationNodeSearchResult.length > 0
        ) {
          cypher = `
            MATCH (source)
            WHERE elementId(source) = $source_id
            MATCH (destination)
            WHERE elementId(destination) = $destination_id
            MERGE (source)-[r:${relationship}]->(destination)
            ON CREATE SET 
                r.created_at = timestamp(),
                r.updated_at = timestamp()
            RETURN source.name AS source, type(r) AS relationship, destination.name AS target
          `;

          params = {
            source_id: sourceNodeSearchResult[0]?.elementId,
            destination_id: destinationNodeSearchResult[0]?.elementId,
            user_id: userId,
          };
        } else {
          cypher = `
            MERGE (n:${sourceType} {name: $source_name, user_id: $user_id})
            ON CREATE SET n.created = timestamp(), n.embedding = $source_embedding
            ON MATCH SET n.embedding = $source_embedding
            MERGE (m:${destinationType} {name: $dest_name, user_id: $user_id})
            ON CREATE SET m.created = timestamp(), m.embedding = $dest_embedding
            ON MATCH SET m.embedding = $dest_embedding
            MERGE (n)-[rel:${relationship}]->(m)
            ON CREATE SET rel.created = timestamp()
            RETURN n.name AS source, type(rel) AS relationship, m.name AS target
          `;

          params = {
            source_name: source,
            dest_name: destination,
            source_embedding: sourceEmbedding,
            dest_embedding: destEmbedding,
            user_id: userId,
          };
        }

        const result = await session.run(cypher, params);
        results.push(result.records);
      }
    } finally {
      await session.close();
    }

    return results;
  }

  private _removeSpacesFromEntities(entityList: any[]) {
    return entityList.map((item) => ({
      ...item,
      source: item.source.toLowerCase().replace(/ /g, "_"),
      relationship: item.relationship.toLowerCase().replace(/ /g, "_"),
      destination: item.destination.toLowerCase().replace(/ /g, "_"),
    }));
  }

  private async _searchSourceNode(
    sourceEmbedding: number[],
    userId: string,
    threshold = 0.9,
  ) {
    const session = this.graph.session();
    try {
      const cypher = `
        MATCH (source_candidate)
        WHERE source_candidate.embedding IS NOT NULL 
        AND source_candidate.user_id = $user_id

        WITH source_candidate,
            round(
                reduce(dot = 0.0, i IN range(0, size(source_candidate.embedding)-1) |
                    dot + source_candidate.embedding[i] * $source_embedding[i]) /
                (sqrt(reduce(l2 = 0.0, i IN range(0, size(source_candidate.embedding)-1) |
                    l2 + source_candidate.embedding[i] * source_candidate.embedding[i])) *
                sqrt(reduce(l2 = 0.0, i IN range(0, size($source_embedding)-1) |
                    l2 + $source_embedding[i] * $source_embedding[i])))
                , 4) AS source_similarity
        WHERE source_similarity >= $threshold

        WITH source_candidate, source_similarity
        ORDER BY source_similarity DESC
        LIMIT 1

        RETURN elementId(source_candidate) as element_id
        `;

      const params = {
        source_embedding: sourceEmbedding,
        user_id: userId,
        threshold,
      };

      const result = await session.run(cypher, params);

      return result.records.map((record) => ({
        elementId: record.get("element_id").toString(),
      }));
    } finally {
      await session.close();
    }
  }

  private async _searchDestinationNode(
    destinationEmbedding: number[],
    userId: string,
    threshold = 0.9,
  ) {
    const session = this.graph.session();
    try {
      const cypher = `
        MATCH (destination_candidate)
        WHERE destination_candidate.embedding IS NOT NULL 
        AND destination_candidate.user_id = $user_id

        WITH destination_candidate,
            round(
                reduce(dot = 0.0, i IN range(0, size(destination_candidate.embedding)-1) |
                    dot + destination_candidate.embedding[i] * $destination_embedding[i]) /
                (sqrt(reduce(l2 = 0.0, i IN range(0, size(destination_candidate.embedding)-1) |
                    l2 + destination_candidate.embedding[i] * destination_candidate.embedding[i])) *
                sqrt(reduce(l2 = 0.0, i IN range(0, size($destination_embedding)-1) |
                    l2 + $destination_embedding[i] * $destination_embedding[i])))
            , 4) AS destination_similarity
        WHERE destination_similarity >= $threshold

        WITH destination_candidate, destination_similarity
        ORDER BY destination_similarity DESC
        LIMIT 1

        RETURN elementId(destination_candidate) as element_id
        `;

      const params = {
        destination_embedding: destinationEmbedding,
        user_id: userId,
        threshold,
      };

      const result = await session.run(cypher, params);

      return result.records.map((record) => ({
        elementId: record.get("element_id").toString(),
      }));
    } finally {
      await session.close();
    }
  }
}
