import { useEffect } from "react";
import { useDispatch } from "react-redux";
import { setStats } from "@/store/actions/statsAction";
import { api } from "@/utils/api";
import { STATS_ENDPOINTS } from "@/utils/api-endpoints";
import { AppDispatch } from "@/store/store";
import { useApiQuery } from "@/hooks/use-api-query";
import { DashboardStats } from "@/types/api";

export function useDashboardStats() {
  const dispatch = useDispatch<AppDispatch>();

  const { data } = useApiQuery<DashboardStats>(
    async () => {
      const res = await api.get<DashboardStats>(STATS_ENDPOINTS.OVERVIEW);
      return res.data;
    },
    { errorToast: "Failed to load dashboard stats" },
  );

  useEffect(() => {
    if (data) dispatch(setStats(data));
  }, [data, dispatch]);
}
