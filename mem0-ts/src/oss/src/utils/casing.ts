function toCamelCase(obj: Record<string, any>): Record<string, any> {
  if (typeof obj !== "object" || obj === null) return obj;

  return Object.fromEntries(
    Object.entries(obj).map(([key, value]) => [
      key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase()),
      value,
    ]),
  );
}

export function toCamelCasePreservingIds(
  payload: Record<string, any>,
): Record<string, any> {
  const { agent_id, run_id, user_id, ...rest } = payload;
  return {
    ...toCamelCase(rest),
    ...(agent_id !== undefined && { agent_id }),
    ...(run_id !== undefined && { run_id }),
    ...(user_id !== undefined && { user_id }),
  };
}
