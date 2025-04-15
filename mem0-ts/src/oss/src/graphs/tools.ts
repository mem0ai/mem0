import { z } from "zod";

export interface GraphToolParameters {
  source: string;
  destination: string;
  relationship: string;
  source_type?: string;
  destination_type?: string;
}

export interface GraphEntitiesParameters {
  entities: Array<{
    entity: string;
    entity_type: string;
  }>;
}

export interface GraphRelationsParameters {
  entities: Array<{
    source: string;
    relationship: string;
    destination: string;
  }>;
}

// --- Zod Schemas for Tool Arguments ---

// Schema for simple relationship arguments (Update, Delete)
export const GraphSimpleRelationshipArgsSchema = z.object({
  source: z
    .string()
    .describe("The identifier of the source node in the relationship."),
  relationship: z
    .string()
    .describe("The relationship between the source and destination nodes."),
  destination: z
    .string()
    .describe("The identifier of the destination node in the relationship."),
});

// Schema for adding a relationship (includes types)
export const GraphAddRelationshipArgsSchema =
  GraphSimpleRelationshipArgsSchema.extend({
    source_type: z
      .string()
      .describe("The type or category of the source node."),
    destination_type: z
      .string()
      .describe("The type or category of the destination node."),
  });

// Schema for extracting entities
export const GraphExtractEntitiesArgsSchema = z.object({
  entities: z
    .array(
      z.object({
        entity: z.string().describe("The name or identifier of the entity."),
        entity_type: z.string().describe("The type or category of the entity."),
      }),
    )
    .describe("An array of entities with their types."),
});

// Schema for establishing relationships
export const GraphRelationsArgsSchema = z.object({
  entities: z
    .array(GraphSimpleRelationshipArgsSchema)
    .describe("An array of relationships (source, relationship, destination)."),
});

// --- Tool Definitions (using JSON schema, keep as is) ---

// Note: The tool definitions themselves still use JSON schema format
// as expected by the LLM APIs. The Zod schemas above are for internal
// validation and potentially for use with Langchain's .withStructuredOutput
// if we adapt it to handle tool calls via schema.

export const UPDATE_MEMORY_TOOL_GRAPH = {
  type: "function",
  function: {
    name: "update_graph_memory",
    description:
      "Update the relationship key of an existing graph memory based on new information.",
    parameters: {
      type: "object",
      properties: {
        source: {
          type: "string",
          description:
            "The identifier of the source node in the relationship to be updated.",
        },
        destination: {
          type: "string",
          description:
            "The identifier of the destination node in the relationship to be updated.",
        },
        relationship: {
          type: "string",
          description:
            "The new or updated relationship between the source and destination nodes.",
        },
      },
      required: ["source", "destination", "relationship"],
      additionalProperties: false,
    },
  },
};

export const ADD_MEMORY_TOOL_GRAPH = {
  type: "function",
  function: {
    name: "add_graph_memory",
    description: "Add a new graph memory to the knowledge graph.",
    parameters: {
      type: "object",
      properties: {
        source: {
          type: "string",
          description:
            "The identifier of the source node in the new relationship.",
        },
        destination: {
          type: "string",
          description:
            "The identifier of the destination node in the new relationship.",
        },
        relationship: {
          type: "string",
          description:
            "The type of relationship between the source and destination nodes.",
        },
        source_type: {
          type: "string",
          description: "The type or category of the source node.",
        },
        destination_type: {
          type: "string",
          description: "The type or category of the destination node.",
        },
      },
      required: [
        "source",
        "destination",
        "relationship",
        "source_type",
        "destination_type",
      ],
      additionalProperties: false,
    },
  },
};

export const NOOP_TOOL = {
  type: "function",
  function: {
    name: "noop",
    description: "No operation should be performed to the graph entities.",
    parameters: {
      type: "object",
      properties: {},
      required: [],
      additionalProperties: false,
    },
  },
};

export const RELATIONS_TOOL = {
  type: "function",
  function: {
    name: "establish_relationships",
    description:
      "Establish relationships among the entities based on the provided text.",
    parameters: {
      type: "object",
      properties: {
        entities: {
          type: "array",
          items: {
            type: "object",
            properties: {
              source: {
                type: "string",
                description: "The source entity of the relationship.",
              },
              relationship: {
                type: "string",
                description:
                  "The relationship between the source and destination entities.",
              },
              destination: {
                type: "string",
                description: "The destination entity of the relationship.",
              },
            },
            required: ["source", "relationship", "destination"],
            additionalProperties: false,
          },
        },
      },
      required: ["entities"],
      additionalProperties: false,
    },
  },
};

export const EXTRACT_ENTITIES_TOOL = {
  type: "function",
  function: {
    name: "extract_entities",
    description: "Extract entities and their types from the text.",
    parameters: {
      type: "object",
      properties: {
        entities: {
          type: "array",
          items: {
            type: "object",
            properties: {
              entity: {
                type: "string",
                description: "The name or identifier of the entity.",
              },
              entity_type: {
                type: "string",
                description: "The type or category of the entity.",
              },
            },
            required: ["entity", "entity_type"],
            additionalProperties: false,
          },
          description: "An array of entities with their types.",
        },
      },
      required: ["entities"],
      additionalProperties: false,
    },
  },
};

export const DELETE_MEMORY_TOOL_GRAPH = {
  type: "function",
  function: {
    name: "delete_graph_memory",
    description: "Delete the relationship between two nodes.",
    parameters: {
      type: "object",
      properties: {
        source: {
          type: "string",
          description: "The identifier of the source node in the relationship.",
        },
        relationship: {
          type: "string",
          description:
            "The existing relationship between the source and destination nodes that needs to be deleted.",
        },
        destination: {
          type: "string",
          description:
            "The identifier of the destination node in the relationship.",
        },
      },
      required: ["source", "relationship", "destination"],
      additionalProperties: false,
    },
  },
};
