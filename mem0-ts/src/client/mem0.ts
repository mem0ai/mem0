import axios from "axios";
import {
  AllUsers,
  PaginatedMemories,
  ProjectOptions,
  Memory,
  MemoryHistory,
  AddMemoryOptions,
  SearchMemoryOptions,
  GetAllMemoryOptions,
  DeleteAllMemoryOptions,
  MemoryUpdateBody,
  ProjectResponse,
  PromptUpdatePayload,
  Webhook,
  WebhookCreatePayload,
  WebhookUpdatePayload,
  Message,
  FeedbackPayload,
  CreateMemoryExportPayload,
  GetMemoryExportPayload,
} from "./mem0.types";
import { captureClientEvent, generateHash } from "./telemetry";
import { camelToSnake, camelToSnakeKeys, snakeToCamelKeys } from "./utils";
import { createExceptionFromResponse, MemoryError } from "../common/exceptions";

// Entity params that must be passed via filters - check both snake_case and camelCase
const ENTITY_PARAMS = [
  "user_id",
  "agent_id",
  "app_id",
  "run_id",
  "userId",
  "agentId",
  "appId",
  "runId",
];

/**
 * Validates that no top-level entity parameters are passed.
 * @throws Error if entity params are found at top level
 */
function rejectTopLevelEntityParams(
  options: Record<string, any> | undefined,
  methodName: string,
): void {
  const invalidKeys = Object.keys(options ?? {}).filter((k) =>
    ENTITY_PARAMS.includes(k),
  );
  if (invalidKeys.length > 0) {
    throw new Error(
      `Top-level entity parameters [${invalidKeys.join(", ")}] are not supported in ${methodName}(). ` +
        `Use filters: { user_id: "..." } instead.`,
    );
  }
}

class APIError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "APIError";
  }
}

interface ClientOptions {
  apiKey: string;
  host?: string;
}

export default class MemoryClient {
  apiKey: string;
  host: string;
  private organizationId: string | number | null;
  private projectId: string | number | null;
  headers: Record<string, string>;
  client: any;
  telemetryId: string;

  _validateApiKey(): any {
    if (!this.apiKey) {
      throw new Error("Mem0 API key is required");
    }
    if (typeof this.apiKey !== "string") {
      throw new Error("Mem0 API key must be a string");
    }
    if (this.apiKey.trim() === "") {
      throw new Error("Mem0 API key cannot be empty");
    }
  }

  constructor(options: ClientOptions) {
    this.apiKey = options.apiKey;
    this.host = options.host || "https://api.mem0.ai";
    this.organizationId = null;
    this.projectId = null;

    this.headers = {
      Authorization: `Token ${this.apiKey}`,
      "Content-Type": "application/json",
    };

    this.client = axios.create({
      baseURL: this.host,
      headers: { Authorization: `Token ${this.apiKey}` },
      timeout: 60000,
    });

    this._validateApiKey();
    this.telemetryId = "";
    this._initializeClient();
  }

  private async _initializeClient() {
    try {
      await this.ping();

      if (!this.telemetryId) {
        this.telemetryId = generateHash(this.apiKey);
      }

      captureClientEvent("init", this, {
        client_type: "MemoryClient",
      }).catch((error: any) => {
        console.error("Failed to capture event:", error);
      });
    } catch (error: any) {
      console.error("Failed to initialize client:", error);
      await captureClientEvent("init_error", this, {
        error: error?.message || "Unknown error",
        stack: error?.stack || "No stack trace",
      });
    }
  }

  private _captureEvent(methodName: string, args: any[]) {
    captureClientEvent(methodName, this, {
      success: true,
      args_count: args.length,
      keys: args.length > 0 ? args[0] : [],
    }).catch((error: any) => {
      console.error("Failed to capture event:", error);
    });
  }

  async _fetchWithErrorHandling(url: string, options: any): Promise<any> {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        Authorization: `Token ${this.apiKey}`,
        "Mem0-User-ID": this.telemetryId,
      },
    });
    if (!response.ok) {
      const errorData = await response.text();
      throw createExceptionFromResponse(response.status, errorData);
    }
    const jsonResponse = await response.json();
    return snakeToCamelKeys(jsonResponse);
  }

  _preparePayload(
    messages: Array<Message>,
    options: Record<string, any>,
  ): object {
    const payload: any = {};
    payload.messages = messages;
    return camelToSnakeKeys({ ...payload, ...options });
  }

  _prepareParams(options: Record<string, any>): object {
    return Object.fromEntries(
      Object.entries(options).filter(([_, v]) => v != null),
    );
  }

  async ping(): Promise<void> {
    try {
      const response = await this._fetchWithErrorHandling(
        `${this.host}/v1/ping/`,
        {
          method: "GET",
          headers: {
            Authorization: `Token ${this.apiKey}`,
          },
        },
      );

      if (!response || typeof response !== "object") {
        throw new APIError("Invalid response format from ping endpoint");
      }

      if (response.status !== "ok") {
        throw new APIError(response.message || "API Key is invalid");
      }

      const { orgId, projectId, userEmail } = response;

      if (orgId) this.organizationId = orgId;
      if (projectId) this.projectId = projectId;
      if (userEmail) this.telemetryId = userEmail;
    } catch (error: any) {
      // Pass through structured exceptions and APIError
      if (error instanceof MemoryError || error instanceof APIError) {
        throw error;
      } else {
        throw new APIError(
          `Failed to ping server: ${error.message || "Unknown error"}`,
        );
      }
    }
  }

  async add(
    messages: Array<Message>,
    options: AddMemoryOptions & Record<string, any> = {},
  ): Promise<Array<Memory>> {
    if (this.telemetryId === "") await this.ping();

    const payload = this._preparePayload(messages, options);
    const payloadKeys = Object.keys(payload);
    this._captureEvent("add", [payloadKeys]);

    const response = await this._fetchWithErrorHandling(
      `${this.host}/v3/memories/add/`,
      {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(payload),
      },
    );
    return response;
  }

  async update(
    memoryId: string,
    {
      text,
      metadata,
      timestamp,
    }: {
      text?: string;
      metadata?: Record<string, any>;
      timestamp?: number | string;
    },
  ): Promise<Array<Memory>> {
    if (
      text === undefined &&
      metadata === undefined &&
      timestamp === undefined
    ) {
      throw new Error(
        "At least one of text, metadata, or timestamp must be provided for update.",
      );
    }

    if (this.telemetryId === "") await this.ping();
    const payload: Record<string, any> = {};
    if (text !== undefined) payload.text = text;
    if (metadata !== undefined) payload.metadata = metadata;
    if (timestamp !== undefined) payload.timestamp = timestamp;

    const payloadKeys = Object.keys(payload);
    this._captureEvent("update", [payloadKeys]);

    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/`,
      {
        method: "PUT",
        headers: this.headers,
        body: JSON.stringify(payload),
      },
    );
    return response;
  }

  async get(memoryId: string): Promise<Memory> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("get", []);
    return this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/`,
      {
        headers: this.headers,
      },
    );
  }

  async getAll(options?: GetAllMemoryOptions): Promise<PaginatedMemories> {
    // Reject top-level entity params - must use filters instead
    rejectTopLevelEntityParams(options as Record<string, any>, "getAll");

    if (this.telemetryId === "") await this.ping();
    const payloadKeys = Object.keys(options || {});
    this._captureEvent("get_all", [payloadKeys]);
    const { page, pageSize, filters, ...rest } = options ?? {};
    const body: Record<string, any> = {
      ...camelToSnakeKeys(rest),
      ...(filters && { filters }),
    };

    let url = `${this.host}/v3/memories/`;
    if (page && pageSize) {
      url += `?page=${page}&page_size=${pageSize}`;
    }

    const response = await this._fetchWithErrorHandling(url, {
      method: "POST",
      headers: this.headers,
      body: JSON.stringify(body),
    });
    return response;
  }

  async search(
    query: string,
    options?: SearchMemoryOptions,
  ): Promise<{ results: Array<Memory> }> {
    // Reject top-level entity params - must use filters instead
    rejectTopLevelEntityParams(options as Record<string, any>, "search");

    if (this.telemetryId === "") await this.ping();
    const payloadKeys = Object.keys(options || {});
    this._captureEvent("search", [payloadKeys]);
    const { filters, ...rest } = options ?? {};
    const payload: Record<string, any> = {
      query,
      output_format: "v1.1",
      ...camelToSnakeKeys(rest),
      ...(filters && { filters }),
    };

    const response = await this._fetchWithErrorHandling(
      `${this.host}/v3/memories/search/`,
      {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(payload),
      },
    );
    return response;
  }

  async delete(memoryId: string): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("delete", []);
    return this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/`,
      {
        method: "DELETE",
        headers: this.headers,
      },
    );
  }

  async deleteAll(
    options: DeleteAllMemoryOptions = {},
  ): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();
    const payloadKeys = Object.keys(options || {});
    this._captureEvent("delete_all", [payloadKeys]);
    const snakeOptions = camelToSnakeKeys(this._prepareParams(options));
    // @ts-ignore
    const params = new URLSearchParams(snakeOptions);
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/memories/?${params}`,
      {
        method: "DELETE",
        headers: this.headers,
      },
    );
    return response;
  }

  async history(memoryId: string): Promise<Array<MemoryHistory>> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("history", []);
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/history/`,
      {
        headers: this.headers,
      },
    );
    return response;
  }

  async users(options?: {
    page?: number;
    pageSize?: number;
  }): Promise<AllUsers> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("users", []);
    let url = `${this.host}/v1/entities/`;
    const params: string[] = [];
    if (options?.page) params.push(`page=${options.page}`);
    if (options?.pageSize) params.push(`page_size=${options.pageSize}`);
    if (params.length) url += `?${params.join("&")}`;
    const response = await this._fetchWithErrorHandling(url, {
      headers: this.headers,
    });
    return response;
  }

  /**
   * @deprecated The method should not be used, use `deleteUsers` instead. This will be removed in version 2.2.0.
   */
  async deleteUser(data: {
    entity_id: number;
    entity_type: string;
  }): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("delete_user", []);
    if (!data.entity_type) {
      data.entity_type = "user";
    }
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/entities/${data.entity_type}/${data.entity_id}/`,
      {
        method: "DELETE",
        headers: this.headers,
      },
    );
    return response;
  }

  async deleteUsers(
    params: {
      userId?: string;
      agentId?: string;
      appId?: string;
      runId?: string;
    } = {},
  ): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();

    let to_delete: Array<{ type: string; name: string }> = [];
    const { userId, agentId, appId, runId } = params;

    if (userId) {
      to_delete = [{ type: "user", name: userId }];
    } else if (agentId) {
      to_delete = [{ type: "agent", name: agentId }];
    } else if (appId) {
      to_delete = [{ type: "app", name: appId }];
    } else if (runId) {
      to_delete = [{ type: "run", name: runId }];
    } else {
      const entities = await this.users();
      to_delete = entities.results.map((entity) => ({
        type: entity.type,
        name: entity.name,
      }));
    }

    if (to_delete.length === 0) {
      throw new Error("No entities to delete");
    }

    for (const entity of to_delete) {
      try {
        await this.client.delete(`/v2/entities/${entity.type}/${entity.name}/`);
      } catch (error: any) {
        throw new APIError(
          `Failed to delete ${entity.type} ${entity.name}: ${error.message}`,
        );
      }
    }

    this._captureEvent("delete_users", [
      { userId, agentId, appId, runId, sync_type: "sync" },
    ]);

    return {
      message:
        userId || agentId || appId || runId
          ? "Entity deleted successfully."
          : "All users, agents, apps and runs deleted.",
    };
  }

  async batchUpdate(memories: Array<MemoryUpdateBody>): Promise<string> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("batch_update", []);
    const memoriesBody = memories.map((memory) => ({
      memory_id: memory.memoryId,
      text: memory.text,
    }));
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/batch/`,
      {
        method: "PUT",
        headers: this.headers,
        body: JSON.stringify({ memories: memoriesBody }),
      },
    );
    return response;
  }

  async batchDelete(memories: Array<string>): Promise<string> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("batch_delete", []);
    const memoriesBody = memories.map((memory) => ({
      memory_id: memory,
    }));
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/batch/`,
      {
        method: "DELETE",
        headers: this.headers,
        body: JSON.stringify({ memories: memoriesBody }),
      },
    );
    return response;
  }

  async getProject(options: ProjectOptions): Promise<ProjectResponse> {
    if (this.telemetryId === "") await this.ping();
    const payloadKeys = Object.keys(options || {});
    this._captureEvent("get_project", [payloadKeys]);
    const { fields } = options;

    if (!(this.organizationId && this.projectId)) {
      throw new Error(
        "organizationId and projectId must be set to access instructions or categories",
      );
    }

    const params = new URLSearchParams();
    fields?.forEach((field) => params.append("fields", camelToSnake(field)));

    const response = await this._fetchWithErrorHandling(
      `${this.host}/api/v1/orgs/organizations/${this.organizationId}/projects/${this.projectId}/?${params.toString()}`,
      {
        headers: this.headers,
      },
    );
    return response;
  }

  async updateProject(
    prompts: PromptUpdatePayload,
  ): Promise<Record<string, any>> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("update_project", []);
    if (!(this.organizationId && this.projectId)) {
      throw new Error(
        "organizationId and projectId must be set to update instructions or categories",
      );
    }

    const response = await this._fetchWithErrorHandling(
      `${this.host}/api/v1/orgs/organizations/${this.organizationId}/projects/${this.projectId}/`,
      {
        method: "PATCH",
        headers: this.headers,
        body: JSON.stringify(camelToSnakeKeys(prompts)),
      },
    );
    return response;
  }

  // WebHooks
  async getWebhooks(data?: { projectId?: string }): Promise<Array<Webhook>> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("get_webhooks", []);
    const project_id = data?.projectId || this.projectId;
    const response = await this._fetchWithErrorHandling(
      `${this.host}/api/v1/webhooks/projects/${project_id}/`,
      {
        headers: this.headers,
      },
    );
    return response;
  }

  async createWebhook(webhook: WebhookCreatePayload): Promise<Webhook> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("create_webhook", []);
    const body = {
      name: webhook.name,
      url: webhook.url,
      event_types: webhook.eventTypes,
    };
    const response = await this._fetchWithErrorHandling(
      `${this.host}/api/v1/webhooks/projects/${this.projectId}/`,
      {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(body),
      },
    );
    return response;
  }

  async updateWebhook(
    webhook: WebhookUpdatePayload,
  ): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("update_webhook", []);
    const body: Record<string, any> = {};
    if (webhook.name != null) body.name = webhook.name;
    if (webhook.url != null) body.url = webhook.url;
    if (webhook.eventTypes != null) body.event_types = webhook.eventTypes;
    const response = await this._fetchWithErrorHandling(
      `${this.host}/api/v1/webhooks/${webhook.webhookId}/`,
      {
        method: "PUT",
        headers: this.headers,
        body: JSON.stringify(body),
      },
    );
    return response;
  }

  async deleteWebhook(data: {
    webhookId: string;
  }): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("delete_webhook", []);
    const webhook_id = data.webhookId || data;
    const response = await this._fetchWithErrorHandling(
      `${this.host}/api/v1/webhooks/${webhook_id}/`,
      {
        method: "DELETE",
        headers: this.headers,
      },
    );
    return response;
  }

  async feedback(data: FeedbackPayload): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();
    const payloadKeys = Object.keys(data || {});
    this._captureEvent("feedback", [payloadKeys]);
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/feedback/`,
      {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(camelToSnakeKeys(data)),
      },
    );
    return response;
  }

  async createMemoryExport(
    data: CreateMemoryExportPayload,
  ): Promise<{ message: string; id: string }> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("create_memory_export", []);

    if (!data.filters || !data.schema) {
      throw new Error("Missing filters or schema");
    }

    const { filters, ...rest } = data;
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/exports/`,
      {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify({
          ...camelToSnakeKeys(rest),
          filters,
        }),
      },
    );

    return response;
  }

  async getMemoryExport(
    data: GetMemoryExportPayload,
  ): Promise<{ message: string; id: string }> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("get_memory_export", []);

    if (!data.memoryExportId && !data.filters) {
      throw new Error("Missing memoryExportId or filters");
    }

    const { filters, ...rest } = data;
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/exports/get/`,
      {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify({
          ...camelToSnakeKeys(rest),
          ...(filters && { filters }),
        }),
      },
    );
    return response;
  }
}

export { MemoryClient };
