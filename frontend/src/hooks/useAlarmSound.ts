import { useEffect, useMemo, useSyncExternalStore } from "react";
import { useAlarmsQuery } from "./useAlarmsQuery";
import { alarmSound, soundworthyIds } from "../lib/alarmSound";

/**
 * Mute/lock state + feeding the shared sound engine (see lib/alarmSound.ts for the rules).
 * Safe to call from several components at once: the engine announces each alarm id only once.
 */
export function useAlarmSound() {
  const { muted, locked } = useSyncExternalStore(alarmSound.subscribe, alarmSound.getSnapshot);
  const { data } = useAlarmsQuery("active"); // same query key everywhere -> one shared request

  useEffect(() => {
    alarmSound.attach();
  }, []);

  useEffect(() => {
    // Only observe REAL data: observing the empty "still loading" array would forget what was announced.
    if (data) alarmSound.observe(data);
  }, [data]);

  const criticalAlarms = useMemo(() => (data ? soundworthyIds(data).size : 0), [data]);

  return { isMuted: muted, toggleMute: alarmSound.toggleMute, criticalAlarms, isAudioLocked: locked };
}
