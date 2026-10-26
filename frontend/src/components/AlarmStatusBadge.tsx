import { statusBadgeClass } from "../lib/alarms";

interface Props {
  status: string;
  /** Show "×N" when the same alarm was reported more than once (de-duplicated recurrences). */
  occurrences?: number;
}

/** Three lifecycle states: active (red) / acknowledged (amber) / resolved (green). */
export default function AlarmStatusBadge({ status, occurrences }: Props) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
      <span className={`badge ${statusBadgeClass(status)}`} style={{ fontSize: "0.7rem" }}>
        {status}
      </span>
      {occurrences && occurrences > 1 ? (
        <span title={`Reported ${occurrences} times`} style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
          ×{occurrences}
        </span>
      ) : null}
    </span>
  );
}
