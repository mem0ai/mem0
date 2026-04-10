export interface Stats {
  memory_count: number;
  team_size: number;
  active_api_keys: number;
}

export enum StatsConstants {
  SET_STATS = "SET_STATS",
}

export interface SetStatsAction {
  type: StatsConstants.SET_STATS;
  payload: Stats;
}

export type StatsActions = SetStatsAction;

export const setStats = (stats: Stats): StatsActions => ({
  type: StatsConstants.SET_STATS,
  payload: stats,
});
