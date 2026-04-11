/**
 * Converts a camelCase string to snake_case.
 */
export function camelToSnake(str: string): string {
  // Skip all-uppercase keys (e.g. OR, AND, NOT — logical operators)
  if (str === str.toUpperCase()) return str;
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

/**
 * Converts a snake_case string to camelCase.
 */
function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

/**
 * Recursively converts all keys of an object from camelCase to snake_case.
 * Used for converting user-facing camelCase params to API snake_case payloads.
 */
export function camelToSnakeKeys(obj: any): any {
  if (obj === null || obj === undefined || typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map(camelToSnakeKeys);
  if (obj instanceof Date) return obj;

  return Object.fromEntries(
    Object.entries(obj).map(([key, value]) => [
      camelToSnake(key),
      camelToSnakeKeys(value),
    ]),
  );
}

/**
 * Recursively converts all keys of an object from snake_case to camelCase.
 * Used for converting API snake_case responses to user-facing camelCase.
 */
export function snakeToCamelKeys(obj: any): any {
  if (obj === null || obj === undefined || typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map(snakeToCamelKeys);
  if (obj instanceof Date) return obj;

  return Object.fromEntries(
    Object.entries(obj).map(([key, value]) => [
      snakeToCamel(key),
      snakeToCamelKeys(value),
    ]),
  );
}
