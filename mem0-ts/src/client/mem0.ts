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
        "Warning: Both organizationName and projectName must be provided together when using either. This will be removedfrom the version 1.0.40. Note that organizationName/projectName are being deprecated in favor of organizationId/projectId.",
      );
    }

    // Check for organizationId/projectId pair
    if (
      (this.organizationId === null && this.projectId !== null) ||
      (this.organizationId !== null && this.projectId === null)
    ) {
      console.warn(
        "Warning: Both organizationId and projectId must be provided together when using either. This will be removedfrom the version 1.0.40.",
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
    this._validateOrgProject();

    // Initialize with a temporary ID that will be updated
    this.telemetryId = "";

    // Initialize the client
    this._initializeClient();
  }

  private async _initializeClient() {
    try {
      // do this only in browser
      if (typeof window !== "undefined") {
        this.telemetryId = await generateHash(this.apiKey);
        await captureClientEvent("init", this);
      }

      // Wrap methods after initialization
      this.add = this.wrapMethod("add", this.add);
      this.get = this.wrapMethod("get", this.get);
      this.getAll = this.wrapMethod("get_all", this.getAll);
      this.search = this.wrapMethod("search", this.search);
      this.delete = this.wrapMethod("delete", this.delete);
      this.deleteAll = this.wrapMethod("delete_all", this.deleteAll);
      this.history = this.wrapMethod("history", this.history);
      this.users = this.wrapMethod("users", this.users);
      this.deleteUser = this.wrapMethod("delete_user", this.deleteUser);
      this.deleteUsers = this.wrapMethod("delete_users", this.deleteUsers);
      this.batchUpdate = this.wrapMethod("batch_update", this.batchUpdate);
      this.batchDelete = this.wrapMethod("batch_delete", this.batchDelete);
      this.getProject = this.wrapMethod("get_project", this.getProject);
      this.updateProject = this.wrapMethod(
        "update_project",
        this.updateProject,
      );
      this.getWebhooks = this.wrapMethod("get_webhook", this.getWebhooks);
      this.createWebhook = this.wrapMethod(
        "create_webhook",
        this.createWebhook,
      );
      this.updateWebhook = this.wrapMethod(
        "update_webhook",
        this.updateWebhook,
      );
      this.deleteWebhook = this.wrapMethod(
        "delete_webhook",
        this.deleteWebhook,
      );
    } catch (error) {
      console.error("Failed to initialize client:", error);
    }
  }

  wrapMethod(methodName: any, method: any) {
    return async function (...args: any) {
      // @ts-ignore
      await captureClientEvent(methodName, this);
      // @ts-ignore
      return method.apply(this, args);
    }.bind(this);
  }

  async _fetchWithErrorHandling(url: string, options: any): Promise<any> {
    const response = await fetch(url, options);
    if (!response.ok) {
      const errorData = await response.text();
      throw new APIError(`API request failed: ${errorData}`);
    }
    const jsonResponse = await response.json();
    return jsonResponse;
  }

  _preparePayload(
    messages: string | Array<{ role: string; content: string }>,
    options: MemoryOptions,
  ): object {
    const payload: any = {};
    if (typeof messages === "string") {
      payload.messages = [{ role: "user", content: messages }];
    } else if (Array.isArray(messages)) {
      payload.messages = messages;
    }
    return { ...payload, ...options };
  }

  _prepareParams(options: MemoryOptions): object {
    return Object.fromEntries(
      Object.entries(options).filter(([_, v]) => v != null),
    );
  }

  async add(
    messages: string | Array<{ role: string; content: string }>,
    options: MemoryOptions = {},
  ): Promise<Array<Memory>> {
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

    const payload = this._preparePayload(messages, options);
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

  async update(memoryId: string, message: string): Promise<Array<Memory>> {
    this._validateOrgProject();
    const payload = {
      text: message,
    };
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
    return this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/`,
      {
        headers: this.headers,
      },
    );
  }

  async getAll(options?: SearchOptions): Promise<Array<Memory>> {
    this._validateOrgProject();
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
    this._validateOrgProject();
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
    return this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/`,
      {
        method: "DELETE",
        headers: this.headers,
      },
    );
  }

  async deleteAll(options: MemoryOptions = {}): Promise<{ message: string }> {
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
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/history/`,
      {
        headers: this.headers,
      },
    );
    return response;
  }

  async users(): Promise<AllUsers> {
    this._validateOrgProject();
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

  async deleteUser(
    entityId: string,
    entity: { type: string } = { type: "user" },
  ): Promise<{ message: string }> {
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/entities/${entity.type}/${entityId}/`,
      {
        method: "DELETE",
        headers: this.headers,
      },
    );
    return response;
  }

  async deleteUsers(): Promise<{ message: string }> {
    this._validateOrgProject();
    const entities = await this.users();

    for (const entity of entities.results) {
      let options: MemoryOptions = {};
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
      await this.client.delete(`/v1/entities/${entity.type}/${entity.id}/`, {
        params: options,
      });
    }
    return { message: "All users, agents, and sessions deleted." };
  }

  async batchUpdate(memories: Array<MemoryUpdateBody>): Promise<string> {
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
    this._validateOrgProject();

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
    this._validateOrgProject();

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
}

export { MemoryClient };
