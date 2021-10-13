export interface IDashboardResponse {
  at: string;
  time_range_in_days: number;
  counts: {
    [key: string]: number;
  };
}
