// Cloudflare Workers compatible version of MemoryClient
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
} from "../client/mem0.types";

class APIError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "APIError";
  }
}

interface CloudflareWorkerClientOptions {
  apiKey: string;
  host?: string;
  organizationName?: string;
  projectName?: string;
  organizationId?: string;
  projectId?: string;
}

/**
 * Cloudflare Workers compatible MemoryClient
 *
 * This client is specifically designed to work in Cloudflare Workers runtime,
 * avoiding Node.js-specific APIs and native bindings. It uses the Web Fetch API
 * and only connects to the hosted Mem0 platform (no local storage).
 *
 * @example
 * ```typescript
 * import { CloudflareWorkerMemoryClient } from 'mem0ai/workers';
 *
 * const client = new CloudflareWorkerMemoryClient({
 *   apiKey: 'your-api-key'
 * });
 *
 * // Add memories
 * await client.add([
 *   { role: 'user', content: 'I love pizza' }
 * ], { user_id: 'user123' });
 *
 * // Search memories
 * const results = await client.search('food preferences', { user_id: 'user123' });
 * ```
 */
export class CloudflareWorkerMemoryClient {
  private apiKey: string;
  private host: string;
  private organizationName: string | null;
  private projectName: string | null;
  private organizationId: string | number | null;
  private projectId: string | number | null;
  private headers: Record<string, string>;
  private telemetryId: string;

  constructor(options: CloudflareWorkerClientOptions) {
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

    this.telemetryId = "";
    this._validateApiKey();
  }

  private _validateApiKey(): void {
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

  private _validateOrgProject(): void {
    // Check for organizationName/projectName pair
    if (
      (this.organizationName === null && this.projectName !== null) ||
      (this.organizationName !== null && this.projectName === null)
    ) {
      console.warn(
        "Warning: Both organizationName and projectName must be provided together when using either.",
      );
    }

    // Check for organizationId/projectId pair
    if (
      (this.organizationId === null && this.projectId !== null) ||
      (this.organizationId !== null && this.projectId === null)
    ) {
      console.warn(
        "Warning: Both organizationId and projectId must be provided together when using either.",
      );
    }
  }

  private async _fetchWithErrorHandling(
    url: string,
    options: any = {},
  ): Promise<any> {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...this.headers,
        ...options.headers,
        "Mem0-User-ID": this.telemetryId,
      },
    });

    if (!response.ok) {
      let errorData: string;
      try {
        errorData = await response.text();
      } catch {
        errorData = `HTTP ${response.status}: ${response.statusText}`;
      }
      throw new APIError(`API request failed: ${errorData}`);
    }

    try {
      const jsonResponse = await response.json();
      return jsonResponse;
    } catch (error) {
      throw new APIError(`Failed to parse JSON response: ${error}`);
    }
  }

  private _preparePayload(
    messages: Array<Message>,
    options: MemoryOptions,
  ): object {
    const payload: any = { messages };
    return { ...payload, ...options };
  }

  private _prepareParams(options: MemoryOptions): Record<string, string> {
    const params: Record<string, string> = {};
    for (const [key, value] of Object.entries(options)) {
      if (value != null) {
        params[key] = String(value);
      }
    }
    return params;
  }

  /**
   * Generate a simple hash for telemetry (Workers-compatible)
   */
  private async _generateHash(input: string): Promise<string> {
    const encoder = new TextEncoder();
    const data = encoder.encode(input);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("")
      .substring(0, 16);
  }

  /**
   * Ping the server to validate API key and get org/project info
   */
  async ping(): Promise<void> {
    try {
      const response = await this._fetchWithErrorHandling(
        `${this.host}/v1/ping/`,
        {
          method: "GET",
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
      if (user_email) {
        this.telemetryId = user_email;
      } else {
        // Generate a telemetry ID from the API key for Workers
        this.telemetryId = await this._generateHash(this.apiKey);
      }
    } catch (error: any) {
      if (error instanceof APIError) {
        throw error;
      } else {
        throw new APIError(
          `Failed to ping server: ${error.message || "Unknown error"}`,
        );
      }
    }
  }

  /**
   * Add memories from messages
   */
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

    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/memories/`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
    return response;
  }

  /**
   * Update a memory by ID
   */
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

    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    );
    return response;
  }

  /**
   * Get a memory by ID
   */
  async get(memoryId: string): Promise<Memory> {
    if (this.telemetryId === "") await this.ping();
    return this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/`,
      { method: "GET" },
    );
  }

  /**
   * Get all memories with optional filtering
   */
  async getAll(options?: SearchOptions): Promise<Array<Memory>> {
    if (this.telemetryId === "") await this.ping();
    this._validateOrgProject();

    const { api_version, page, page_size, ...otherOptions } = options || {};

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
      const url = paginated_response
        ? `${this.host}/v2/memories/?${appendedParams}`
        : `${this.host}/v2/memories/`;
      return this._fetchWithErrorHandling(url, {
        method: "POST",
        body: JSON.stringify(otherOptions),
      });
    } else {
      const params = new URLSearchParams(
        this._prepareParams(otherOptions as MemoryOptions),
      );
      const url = paginated_response
        ? `${this.host}/v1/memories/?${params}&${appendedParams}`
        : `${this.host}/v1/memories/?${params}`;
      return this._fetchWithErrorHandling(url, { method: "GET" });
    }
  }

  /**
   * Search memories by query
   */
  async search(query: string, options?: SearchOptions): Promise<Array<Memory>> {
    if (this.telemetryId === "") await this.ping();
    this._validateOrgProject();

    const { api_version, ...otherOptions } = options || {};
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
        body: JSON.stringify(payload),
      },
    );
    return response;
  }

  /**
   * Delete a memory by ID
   */
  async delete(memoryId: string): Promise<{ message: string }> {
    if (this.telemetryId === "") await this.ping();
    return this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/`,
      { method: "DELETE" },
    );
  }

  /**
   * Delete all memories with optional filtering
   */
  async deleteAll(options: MemoryOptions = {}): Promise<{ message: string }> {
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

    const params = new URLSearchParams(this._prepareParams(options));
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/memories/?${params}`,
      { method: "DELETE" },
    );
    return response;
  }

  /**
   * Get memory history by ID
   */
  async history(memoryId: string): Promise<Array<MemoryHistory>> {
    if (this.telemetryId === "") await this.ping();
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/memories/${memoryId}/history/`,
      { method: "GET" },
    );
    return response;
  }

  /**
   * Get all users/entities
   */
  async users(): Promise<AllUsers> {
    if (this.telemetryId === "") await this.ping();
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

    const params = new URLSearchParams(this._prepareParams(options));
    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/entities/?${params}`,
      { method: "GET" },
    );
    return response;
  }

  /**
   * Batch update multiple memories
   */
  async batchUpdate(memories: Array<MemoryUpdateBody>): Promise<string> {
    if (this.telemetryId === "") await this.ping();

    const memoriesBody = memories.map((memory) => ({
      memory_id: memory.memoryId,
      text: memory.text,
    }));

    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/batch/`,
      {
        method: "PUT",
        body: JSON.stringify({ memories: memoriesBody }),
      },
    );
    return response;
  }

  /**
   * Batch delete multiple memories
   */
  async batchDelete(memories: Array<string>): Promise<string> {
    if (this.telemetryId === "") await this.ping();

    const memoriesBody = memories.map((memory) => ({
      memory_id: memory,
    }));

    const response = await this._fetchWithErrorHandling(
      `${this.host}/v1/batch/`,
      {
        method: "DELETE",
        body: JSON.stringify({ memories: memoriesBody }),
      },
    );
    return response;
  }
}

// Re-export types for convenience
export type {
  MemoryOptions,
  ProjectOptions,
  Memory,
  MemoryHistory,
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
  AllUsers,
} from "../client/mem0.types";

export default CloudflareWorkerMemoryClient;
