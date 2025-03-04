export interface Logger {
  info: (message: string) => void;
  error: (message: string) => void;
  debug: (message: string) => void;
  warn: (message: string) => void;
}

export const logger: Logger = {
  info: (message: string) => console.log(`[INFO] ${message}`),
  error: (message: string) => console.error(`[ERROR] ${message}`),
  debug: (message: string) => console.debug(`[DEBUG] ${message}`),
  warn: (message: string) => console.warn(`[WARN] ${message}`),
};
