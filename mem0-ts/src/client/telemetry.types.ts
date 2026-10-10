export interface TelemetryClient {
  captureEvent(
    distinctId: string,
    eventName: string,
    properties?: Record<string, any>,
  ): Promise<boolean>;
  shutdown(): Promise<void>;
}
