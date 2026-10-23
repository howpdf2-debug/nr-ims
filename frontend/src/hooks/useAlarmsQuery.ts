import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Alarm, AlarmStatusFilter } from "../lib/alarms";

export interface AlarmsQueryOptions {
  /** Set false to skip the request (e.g. a tab that is not visible). */
  enabled?: boolean;
  limit?: number;
}

/**
 * Alarms from `GET /alarms/?status=<filter>`. The filter is part of the query key, so each status has its own
 * cache entry, and invalidating `["alarms"]` refreshes all of them.
 * `open` (default) = active + acknowledged; the sound engine and the Wallboard ask for `active` only.
 */
export function useAlarmsQuery(status: AlarmStatusFilter = "open", options: AlarmsQueryOptions = {}) {
  const { enabled = true, limit = 500 } = options;
  return useQuery<Alarm[]>({
    queryKey: ["alarms", status, limit],
    queryFn: () => api.get<Alarm[]>("/alarms/", { params: { status, limit } }).then((res) => res.data),
    enabled,
    refetchInterval: 10000,
    staleTime: 5000,
    refetchOnWindowFocus: false,
  });
}
