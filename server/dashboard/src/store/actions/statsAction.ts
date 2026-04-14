import { DashboardStats } from "@/types/api";

export enum StatsConstants {
  SET_STATS = "SET_STATS",
}

export interface SetStatsAction {
  type: StatsConstants.SET_STATS;
  payload: DashboardStats;
}

export type StatsActions = SetStatsAction;

export const setStats = (stats: DashboardStats): StatsActions => ({
  type: StatsConstants.SET_STATS,
  payload: stats,
});
