"""Root-cause correlation: an alarm is suppressed when any ancestor station is itself down."""

from collections.abc import Iterable


def find_root_cause(station_code: str, parent_of: dict[str, str | None],
                    stations_with_active_alarms: set[str]) -> str | None:
    """Walk up the station hierarchy; return the nearest-to-root ancestor that is alarming."""
    seen: set[str] = {station_code}
    cursor = parent_of.get(station_code)
    root = None
    while cursor and cursor not in seen:  # cycle-safe
        if cursor in stations_with_active_alarms:
            root = cursor
        seen.add(cursor)
        cursor = parent_of.get(cursor)
    return root


def build_parent_map(rows: Iterable[tuple[str, str | None]]) -> dict[str, str | None]:
    return dict(rows)
