import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export function useAlarmsQuery() {
  return useQuery({
    queryKey: ["alarms"],
    queryFn: () => api.get("/alarms/").then((res) => res.data),
    refetchInterval: 10000,
    staleTime: 5000,
    refetchOnWindowFocus: false,
  });
}
