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
}
