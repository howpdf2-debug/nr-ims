"""Counter -> rate maths for interface polling (Phase 3a-1). Pure functions, no I/O, fully unit-tested.

Why this is its own module: wrong rates are worse than no rates. Operators will act on "link is at 97%",
so every ambiguous case returns ``None`` (= "no reliable value this cycle") instead of a guess:

* first sample (nothing to subtract from)                       -> None
* non-positive or too-long gap between samples (> 15 min)       -> None
* device rebooted (sysUpTime went backwards): counters restart  -> None
* 64-bit counter went backwards                                 -> None (64-bit counters do not wrap)
* 32-bit counter went backwards: a wrap IF the implied rate is physically possible for the line speed,
  otherwise a counter reset                                      -> None
* a delta larger than the line could carry in the interval      -> None (glitch)
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_GAP_S = 900.0
_U32 = 1 << 32


@dataclass(frozen=True)
class CounterSnapshot:
    ts: float  # epoch seconds when the sample was taken
    uptime_s: float | None  # sysUpTime in seconds (None when the device did not report it)
    in_octets: int
    out_octets: int
    in_errors: int
    out_errors: int
    in_discards: int
    out_discards: int
    bits: int  # width of the octet counters: 64 (ifHCInOctets) or 32 (ifInOctets)


@dataclass(frozen=True)
class InterfaceRates:
    in_bps: int | None
    out_bps: int | None
    in_util_pct: float | None
    out_util_pct: float | None
    in_errors: int | None  # deltas over the interval
    out_errors: int | None
    in_discards: int | None
    out_discards: int | None


def counter_delta(prev: int, curr: int, bits: int, *, max_plausible: int | None = None) -> int | None:
    """Difference between two counter readings, or ``None`` when it cannot be trusted."""
    if prev < 0 or curr < 0:
        return None
    if curr >= prev:
        delta = curr - prev
    elif bits == 32:
        delta = curr + _U32 - prev  # candidate wrap; validated below
    else:
        return None
    if max_plausible is not None and delta > max_plausible:
        return None
    return delta


def compute_interface_rates(prev: CounterSnapshot | None, curr: CounterSnapshot,
                            speed_mbps: int | None) -> InterfaceRates | None:
    """Rates between two snapshots of ONE interface, or ``None`` when there is no reliable value."""
    if prev is None:
        return None
    dt = curr.ts - prev.ts
    if dt <= 0 or dt > MAX_GAP_S:
        return None
    if prev.uptime_s is not None and curr.uptime_s is not None and curr.uptime_s < prev.uptime_s:
        return None  # reboot
    if prev.bits != curr.bits:
        return None  # counter source changed (e.g. HC counters appeared after an upgrade)

    speed_bps = speed_mbps * 1_000_000 if speed_mbps and speed_mbps > 0 else None
    # A link cannot move more octets than line-rate x time. 1.5x + one frame of slack absorbs timing jitter.
    max_octets = int(speed_bps / 8 * dt * 1.5) + 1500 if speed_bps else None

    d_in = counter_delta(prev.in_octets, curr.in_octets, curr.bits, max_plausible=max_octets)
    d_out = counter_delta(prev.out_octets, curr.out_octets, curr.bits, max_plausible=max_octets)
    in_bps = int(d_in * 8 / dt) if d_in is not None else None
    out_bps = int(d_out * 8 / dt) if d_out is not None else None

    def util(bps: int | None) -> float | None:
        if bps is None or not speed_bps:
            return None
        return round(min(100.0, bps / speed_bps * 100), 2)

    return InterfaceRates(
        in_bps=in_bps, out_bps=out_bps, in_util_pct=util(in_bps), out_util_pct=util(out_bps),
        in_errors=counter_delta(prev.in_errors, curr.in_errors, 32),
        out_errors=counter_delta(prev.out_errors, curr.out_errors, 32),
        in_discards=counter_delta(prev.in_discards, curr.in_discards, 32),
        out_discards=counter_delta(prev.out_discards, curr.out_discards, 32),
    )
