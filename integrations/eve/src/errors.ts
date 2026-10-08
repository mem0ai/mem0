export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown Mem0 error";
}

export function isSetupError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const text = `${error.name} ${error.message}`.toLowerCase();
  return (
    text.includes("api key") ||
    text.includes("cannot be empty") ||
    text.includes("authentication") ||
    text.includes("unauthorized") ||
    text.includes("401") ||
    text.includes("403")
  );
}

export function isNotFoundError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const text = `${error.name} ${error.message}`.toLowerCase();
  return text.includes("not found") || text.includes("404");
}

export function logProviderError(
  scope: string,
  error: unknown,
  extra: Readonly<Record<string, unknown>>,
): void {
  console.error(`[@mem0/eve] ${scope}`, {
    error,
    name: error instanceof Error ? error.name : undefined,
    message: errorMessage(error),
    ...extra,
  });
}
