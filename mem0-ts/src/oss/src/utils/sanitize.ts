// packages/mem0-ts/src/utils/sanitize.ts
export function toPlainObject<T>(obj: T): T {
  // cheap and safe approach: JSON roundtrip (removes prototypes + functions).
  // If you need to preserve Dates or other types, use a custom serializer.
  return JSON.parse(JSON.stringify(obj)) as T;
}

// Use this before returning objects from any provider function that will be consumed by a Worker or cross-runtime boundary.
