import { useEffect, useRef } from "react";
import { useDispatch } from "react-redux";
import { setStats } from "@/store/actions/statsAction";
import { api } from "@/utils/api";
import { STATS_ENDPOINTS } from "@/utils/api-endpoints";
import { AppDispatch } from "@/store/store";

export function useDashboardStats() {
  const dispatch = useDispatch<AppDispatch>();
  const isFetchingRef = useRef(false);

  useEffect(() => {
    const fetchStatsData = async () => {
      if (isFetchingRef.current) return;
      isFetchingRef.current = true;
      try {
        const response = await api.get(STATS_ENDPOINTS.OVERVIEW);
        dispatch(setStats(response.data));
      } catch (error) {
        console.error("Error fetching dashboard stats:", error);
      } finally {
        isFetchingRef.current = false;
      }
    };
    fetchStatsData();
  }, [dispatch]);
}
