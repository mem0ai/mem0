import axios from "axios";
import { useCallback, useEffect, useState } from "react";

export interface UserStats {
  user_id: string;
  memory_count: number;
  last_active_at: string | null;
}

const URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765";

/**
 * Fetches the list of distinct user_ids known to the backend.
 *
 * Used by the UserSelector to render a combobox of known scopes (e.g.
 * "TpGroup", "OtherProject"). Pass `includeEmpty=true` to also list users
 * that have zero live memories — useful right after a fresh install.
 */
export function useUsers(includeEmpty = false) {
  const [users, setUsers] = useState<UserStats[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await axios.get<UserStats[]>(`${URL}/api/v1/users/`, {
        params: { include_empty: includeEmpty },
      });
      setUsers(res.data);
    } catch (err: any) {
      setError(err?.message || "Failed to fetch users");
    } finally {
      setIsLoading(false);
    }
  }, [includeEmpty]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  return { users, isLoading, error, refetch: fetchUsers };
}
