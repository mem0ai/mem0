export interface TelemetryClient {
  captureEvent(
    distinctId: string,
    eventName: string,
    properties?: Record<string, any>,
  ): Promise<void>;
  shutdown(): Promise<void>;
}

export interface TelemetryInstance {
  telemetryId: string;
  constructor: {
    name: string;
  };
  host?: string;
  apiKey?: string;
}

export interface TelemetryEventData {
  function: string;
  method: string;
  api_host?: string;
  timestamp?: string;
  client_source: "browser" | "nodejs";
  client_version: string;
  [key: string]: any;
}

export interface TelemetryOptions {
  enabled?: boolean;
  apiKey?: string;
  host?: string;
  version?: string;
}
