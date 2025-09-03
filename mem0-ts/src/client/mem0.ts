import axios from "axios";
import {
  AllUsers,
  ProjectOptions,
  Memory,
  MemoryHistory,
  MemoryOptions,
  MemoryUpdateBody,
  ProjectResponse,
  PromptUpdatePayload,
  SearchOptions,
  Webhook,
  WebhookPayload,
  Message,
  FeedbackPayload,
  CreateMemoryExportPayload,
  GetMemoryExportPayload,
} from "./mem0.types";
import { captureClientEvent, generateHash } from "./telemetry";

class APIError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "APIError";
  }
}

interface ClientOptions {
  apiKey: string;
  host?: string;
  organizationName?: string;
  projectName?: string;
  organizationId?: string;
  projectId?: string;
}

export default class MemoryClient {
  apiKey: string;
  host: string;
  organizationName: string | null;
  projectName: string | null;
  organizationId: string | number | null;
  projectId: string | number | null;
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

  _validateOrgProject(): void {
    // Check for organizationName/projectName pair
    if (
      (this.organizationName === null && this.projectName !== null) ||
      (this.organizationName !== null && this.projectName === null)
    ) {
      console.warn(
        "Warning: Both organizationName and projectName must be provided together when using either. This will be removed from version 1.0.40. Note that organizationName/projectName are being deprecated in favor of organizationId/projectId.",
      );
    }

    // Check for organizationId/projectId pair
    if (
      (this.organizationId === null && this.projectId !== null) ||
      (this.organizationId !== null && this.projectId === null)
    ) {
      console.warn(
        "Warning: Both organizationId and projectId must be provided together when using either. This will be removed from version 1.0.40.",
      );
    }
  }

  constructor(options: ClientOptions) {
    this.apiKey = options.apiKey;
    this.host = options.host || "https://api.mem0.ai";
    this.organizationName = options.organizationName || null;
    this.projectName = options.projectName || null;
    this.organizationId = options.organizationId || null;
    this.projectId = options.projectId || null;

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

    // Initialize with a temporary ID that will be updated
    this.telemetryId = "";

    // Initialize the client
    this._initializeClient();
  }

  private async _initializeClient() {
    try {
      // Generate telemetry ID
      await this.ping();

      if (!this.telemetryId) {
        this.telemetryId = generateHash(this.apiKey);
      }

      this._validateOrgProject();

      // Capture initialization event
      captureClientEvent("init", this, {
        api_version: "v1",
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
      throw new APIError(`API request failed: ${errorData}`);
    }
    const jsonResponse = await response.json();
    return jsonResponse;
  }

  _preparePayload(messages: Array<Message>, options: MemoryOptions): object {
    const payload: any = {};
    payload.messages = messages;
    return { ...payload, ...options };
  }

  _prepareParams(options: MemoryOptions): object {
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

      const { org_id, project_id, user_email } = response;

      // Only update if values are actually present
      if (org_id && !this.organizationId) this.organizationId = org_id;
      if (project_id && !this.projectId) this.projectId = project_id;
      if (user_email) this.telemetryId = user_email;
    } catch (error: any) {
      // Convert generic errors to APIError with meaningful messages
      if (error instanceof APIError) {
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
    options: MemoryOptions = {},
  ): Promise<Array<Memory>> {
    if (this.telemetryId === "") await this.ping();
    this._validateOrgProject();
    if (this.organizationName != null && this.projectName != null) {
      options.org_name = this.organizationName;
      options.project_name = this.projectName;
    }

    if (this.organizationId != null && this.projectId != null) {
      options.org_id = this.organizationId;
      options.project_id = this.projectId;

      if (options.org_name) delete options.org_name;
      if (options.project_name) delete options.project_name;
    }

    if (options.api_version) {
      options.version = options.api_version.toString() || "v2";
    }

    const payload = this._preparePayload(messages, options);

    // get payload keys whose value is not null or undefined
    const payloadKeys = Object.keys(payload);
    this._captureEvent("add", [payloadKeys]);

    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/memories/`,
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
    { text, metadata }: { text?: string; metadata?: Record<string, any> },
  ): Promise<Array<Memory>> {
    if (text === undefined && metadata === undefined) {
      throw new Error("Either text or metadata must be provided for update.");
    }

    if (this.telemetryId === "") await this.ping();
    this._validateOrgProject();
    const payload = {
      text: text,
      metadata: metadata,
    };

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

  async getAll(options?: SearchOptions): Promise<Array<Memory>> {
    if (this.telemetryId === "") await this.ping();
    this._validateOrgProject();
    const payloadKeys = Object.keys(options || {});
    this._captureEvent("get_all", [payloadKeys]);
    const { api_version, page, page_size, ...otherOptions } = options!;
    if (this.organizationName != null && this.projectName != null) {
      otherOptions.org_name = this.organizationName;
      otherOptions.project_name = this.projectName;
    }

    let appendedParams = "";
    let paginated_response = false;

    if (page && page_size) {
      appendedParams += `page=${page}&page_size=${page_size}`;
      paginated_response = true;
    }

    if (this.organizationId != null && this.projectId != null) {
      otherOptions.org_id = this.organizationId;
      otherOptions.project_id = this.projectId;

      if (otherOptions.org_name) delete otherOptions.org_name;
      if (otherOptions.project_name) delete otherOptions.project_name;
    }

    if (api_version === "v2") {
      let url = paginated_response
        ? `${this.host}/v2/memories/?${appendedParams}`
        : `${this.host}/v2/memories/`;
      return this._fetchWithErrorHandling(url, {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(otherOptions),
      });
    } else {
      // @ts-ignore
      const params = new URLSearchParams(this._prepareParams(otherOptions));
      const url = paginated_response
        ? `${this.host}/v1/memories/?${params}&${appendedParams}`
        : `${this.host}/v1/memories/?${params}`;
      return this._fetchWithErrorHandling(url, {
        headers: this.headers,
      });
    }
  }

  async search(query: string, options?: SearchOptions): Promise<Array<Memory>> {
    if (this.telemetryId === "") await this.ping();
    this._validateOrgProject();
    const payloadKeys = Object.keys(options || {});
    this._captureEvent("search", [payloadKeys]);
    const { api_version, ...otherOptions } = options!;
    const payload = { query, ...otherOptions };
    if (this.organizationName != null && this.projectName != null) {
      payload.org_name = this.organizationName;
      payload.project_name = this.projectName;
    }

    if (this.organizationId != null && this.projectId != null) {
      payload.org_id = this.organizationId;
      payload.project_id = this.projectId;

      if (payload.org_name) delete payload.org_name;
      if (payload.project_name) delete payload.project_name;
    }
    const endpoint =
      api_version === "v2" ? "/v2/memories/search/" : "/v1/memories/search/";
    const response = await this._fetchWithErrorHandling(
      `${this.host}${endpoint}`,
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

  async deleteAll(options: MemoryOptions = {}): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();
    this._validateOrgProject();
    const payloadKeys = Object.keys(options || {});
    this._captureEvent("delete_all", [payloadKeys]);
    if (this.organizationName != null && this.projectName != null) {
      options.org_name = this.organizationName;
      options.project_name = this.projectName;
    }

    if (this.organizationId != null && this.projectId != null) {
      options.org_id = this.organizationId;
      options.project_id = this.projectId;

      if (options.org_name) delete options.org_name;
      if (options.project_name) delete options.project_name;
    }
    // @ts-ignore
    const params = new URLSearchParams(this._prepareParams(options));
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

  async users(): Promise<AllUsers> {
    if (this.telemetryId === "") await this.ping();
    this._validateOrgProject();
    this._captureEvent("users", []);
    const options: MemoryOptions = {};
    if (this.organizationName != null && this.projectName != null) {
      options.org_name = this.organizationName;
      options.project_name = this.projectName;
    }

    if (this.organizationId != null && this.projectId != null) {
      options.org_id = this.organizationId;
      options.project_id = this.projectId;

      if (options.org_name) delete options.org_name;
      if (options.project_name) delete options.project_name;
    }
    // @ts-ignore
    const params = new URLSearchParams(options);
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/entities/?${params}`,
      {
        headers: this.headers,
      },
    );
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
      user_id?: string;
      agent_id?: string;
      app_id?: string;
      run_id?: string;
    } = {},
  ): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();
    this._validateOrgProject();

    let to_delete: Array<{ type: string; name: string }> = [];
    const { user_id, agent_id, app_id, run_id } = params;

    if (user_id) {
      to_delete = [{ type: "user", name: user_id }];
    } else if (agent_id) {
      to_delete = [{ type: "agent", name: agent_id }];
    } else if (app_id) {
      to_delete = [{ type: "app", name: app_id }];
    } else if (run_id) {
      to_delete = [{ type: "run", name: run_id }];
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

    const requestOptions: MemoryOptions = {};
    if (this.organizationName != null && this.projectName != null) {
      requestOptions.org_name = this.organizationName;
      requestOptions.project_name = this.projectName;
    }

    if (this.organizationId != null && this.projectId != null) {
      requestOptions.org_id = this.organizationId;
      requestOptions.project_id = this.projectId;

      if (requestOptions.org_name) delete requestOptions.org_name;
      if (requestOptions.project_name) delete requestOptions.project_name;
    }

    // Delete each entity and handle errors
    for (const entity of to_delete) {
      try {
        await this.client.delete(
          `/v2/entities/${entity.type}/${entity.name}/`,
          {
            params: requestOptions,
          },
        );
      } catch (error: any) {
        throw new APIError(
          `Failed to delete ${entity.type} ${entity.name}: ${error.message}`,
        );
      }
    }

    this._captureEvent("delete_users", [
      {
        user_id: user_id,
        agent_id: agent_id,
        app_id: app_id,
        run_id: run_id,
        sync_type: "sync",
      },
    ]);

    return {
      message:
        user_id || agent_id || app_id || run_id
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
    this._validateOrgProject();
    const payloadKeys = Object.keys(options || {});
    this._captureEvent("get_project", [payloadKeys]);
    const { fields } = options;

    if (!(this.organizationId && this.projectId)) {
      throw new Error(
        "organizationId and projectId must be set to access instructions or categories",
      );
    }

    const params = new URLSearchParams();
    fields?.forEach((field) => params.append("fields", field));

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
    this._validateOrgProject();
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
        body: JSON.stringify(prompts),
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

  async createWebhook(webhook: WebhookPayload): Promise<Webhook> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("create_webhook", []);
    const response = await this._fetchWithErrorHandling(
      `${this.host}/api/v1/webhooks/projects/${this.projectId}/`,
      {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(webhook),
      },
    );
    return response;
  }

  async updateWebhook(webhook: WebhookPayload): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("update_webhook", []);
    const project_id = webhook.projectId || this.projectId;
    const response = await this._fetchWithErrorHandling(
      `${this.host}/api/v1/webhooks/${webhook.webhookId}/`,
      {
        method: "PUT",
        headers: this.headers,
        body: JSON.stringify({
          ...webhook,
          projectId: project_id,
        }),
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
        body: JSON.stringify(data),
      },
    );
    return response;
  }

  async createMemoryExport(
    data: CreateMemoryExportPayload,
  ): Promise<{ message: string; id: string }> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("create_memory_export", []);

    // Return if missing filters or schema
    if (!data.filters || !data.schema) {
      throw new Error("Missing filters or schema");
    }

    // Add Org and Project ID
    data.org_id = this.organizationId?.toString() || null;
    data.project_id = this.projectId?.toString() || null;

    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/exports/`,
      {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(data),
      },
    );

    return response;
  }

  async getMemoryExport(
    data: GetMemoryExportPayload,
  ): Promise<{ message: string; id: string }> {
    if (this.telemetryId === "") await this.ping();
    this._captureEvent("get_memory_export", []);

    if (!data.memory_export_id && !data.filters) {
      throw new Error("Missing memory_export_id or filters");
    }

    data.org_id = this.organizationId?.toString() || "";
    data.project_id = this.projectId?.toString() || "";

    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/exports/get/`,
      {
        method: "POST",
        headers: this.headers,
        body: JSON.stringify(data),
      },
    );
    return response;
  }
}

export { MemoryClient };
