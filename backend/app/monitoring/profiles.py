"""Vendor profiles: which OIDs carry CPU / memory / temperature (Phase 3a-1).

The data lives in ``profiles.toml`` (editable without touching code, see its header). This module loads and
VALIDATES it (a typo fails at start-up with a readable message, never at 3 a.m. during a poll), selects the
right profile for a device, and turns raw SNMP values into clean percentages / degrees.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

PACKAGED_PROFILES = Path(__file__).with_name("profiles.toml")
_OID_RE = re.compile(r"^\d+(\.\d+){5,}$")  # >= 6 arcs: rejects truncated/typo OIDs like 1.3.6
_PREFIX_RE = re.compile(r"^\d+(\.\d+)*\.$")
_DESCR_LIMIT = 512  # sysDescr is device-controlled input: never feed unbounded text to a regex


class ProfileError(ValueError):
    """profiles.toml is missing, malformed or inconsistent."""


class SnmpReader(Protocol):
    """What profile code needs from an SNMP client (the real one lives in app.services.snmp_v3)."""

    async def get_optional(self, oid: str) -> Any: ...

    async def walk(self, oid: str, max_rows: int = 512) -> list[tuple[tuple[int, ...], Any]]: ...


class MetricSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oid: str
    mode: Literal["scalar", "walk"] = "scalar"
    aggregate: Literal["max", "avg", "min", "first"] = "max"
    scale: float = 1.0
    invert_percent: bool = False
    ignore_zero: bool = False

    @field_validator("oid")
    @classmethod
    def _numeric_oid(cls, v: str) -> str:
        v = v.strip().lstrip(".")
        if not _OID_RE.match(v):
            raise ValueError(f"OID must be dotted-numeric like 1.3.6.1.4.1.9.9.109.1.1.1.1.8, got {v!r}")
        return v


class MemorySpec(BaseModel):
    """Exactly one of: ``percent`` | ``used``+``free`` | ``total``+``available``."""

    model_config = ConfigDict(extra="forbid")

    percent: MetricSource | None = None
    used: MetricSource | None = None
    free: MetricSource | None = None
    total: MetricSource | None = None
    available: MetricSource | None = None

    @model_validator(mode="after")
    def _one_shape(self) -> MemorySpec:
        shapes = [self.percent is not None, self.used is not None and self.free is not None,
                  self.total is not None and self.available is not None]
        given = {k for k, v in self.model_dump(exclude_none=True).items()}
        allowed = [{"percent"}, {"used", "free"}, {"total", "available"}]
        if sum(shapes) != 1 or given not in allowed:
            raise ValueError("memory needs exactly one of: percent | used + free | total + available")
        return self


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$")
    default: bool = False
    inherits: str | None = None
    sys_object_id_prefix: str | None = None
    sys_descr_regex: str | None = None
    cpu: list[MetricSource] = Field(default_factory=list)
    memory: list[MemorySpec] = Field(default_factory=list)
    temperature: list[MetricSource] = Field(default_factory=list)
    notes: str = ""

    @field_validator("sys_object_id_prefix")
    @classmethod
    def _prefix(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lstrip(".")
        if not v.endswith("."):
            v += "."  # "1.3.6.1.4.1.9" must not match enterprise 90
        if not _PREFIX_RE.match(v):
            raise ValueError(f"sys_object_id_prefix must look like 1.3.6.1.4.1.9., got {v!r}")
        return v

    @field_validator("sys_descr_regex")
    @classmethod
    def _regex(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                re.compile(v)
            except re.error as exc:
                raise ValueError(f"invalid regular expression: {exc}") from exc
        return v


class ProfileRegistry:
    def __init__(self, profiles: list[Profile]) -> None:
        names = [p.name for p in profiles]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ProfileError(f"duplicate profile name(s): {dupes}")
        defaults = [p for p in profiles if p.default]
        if len(defaults) != 1:
            raise ProfileError("exactly one profile must have default = true")
        by_name = {p.name: p for p in profiles}
        resolved: list[Profile] = []
        for p in profiles:
            if p.inherits:
                parent = by_name.get(p.inherits)
                if parent is None:
                    raise ProfileError(f"profile {p.name!r} inherits unknown profile {p.inherits!r}")
                if parent.inherits:
                    raise ProfileError(f"profile {p.name!r}: inheriting from an inheriting profile is not supported")
                p = p.model_copy(update={"cpu": p.cpu or parent.cpu, "memory": p.memory or parent.memory,
                                         "temperature": p.temperature or parent.temperature})
            resolved.append(p)
        self.profiles = resolved
        self.default = next(p for p in resolved if p.default)
        self._regex = {p.name: re.compile(p.sys_descr_regex) for p in resolved if p.sys_descr_regex}

    @property
    def names(self) -> list[str]:
        return [p.name for p in self.profiles]

    def select(self, sys_object_id: str | None, sys_descr: str | None) -> Profile:
        oid = (sys_object_id or "").strip().lstrip(".")
        descr = (sys_descr or "")[:_DESCR_LIMIT]
        for p in self.profiles:
            if p.default:
                continue
            if p.sys_object_id_prefix and oid.startswith(p.sys_object_id_prefix):
                return p
            if p.name in self._regex and self._regex[p.name].search(descr):
                return p
        return self.default

    @classmethod
    def load(cls, path: Path | None = None) -> ProfileRegistry:
        path = path or PACKAGED_PROFILES
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ProfileError(f"cannot read profiles file {path}: {exc.strerror}") from None
        except tomllib.TOMLDecodeError as exc:
            raise ProfileError(f"{path}: invalid TOML: {exc}") from None
        if raw.get("version") != 1:
            raise ProfileError(f"{path}: unsupported or missing `version` (expected 1)")
        items = raw.get("profile")
        if not isinstance(items, list) or not items:
            raise ProfileError(f"{path}: no [[profile]] blocks found")
        profiles: list[Profile] = []
        for i, item in enumerate(items, 1):
            label = item.get("name", f"#{i}") if isinstance(item, dict) else f"#{i}"
            try:
                profiles.append(Profile.model_validate(item))
            except ValidationError as exc:
                problems = "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors())
                raise ProfileError(f"{path}: profile {label!r}: {problems}") from None
        return cls(profiles)


# ── turning raw SNMP values into clean numbers ──────────────────────────────────────────────────
def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def reduce_values(src: MetricSource, values: list[Any]) -> float | None:
    """Aggregate raw readings of one source into one number (scale / invert applied)."""
    nums = [n for n in (_num(v) for v in values) if n is not None]
    if src.ignore_zero:
        nums = [n for n in nums if n != 0]
    if not nums:
        return None
    if src.aggregate == "max":
        out = max(nums)
    elif src.aggregate == "min":
        out = min(nums)
    elif src.aggregate == "avg":
        out = sum(nums) / len(nums)
    else:
        out = nums[0]
    out *= src.scale
    return 100.0 - out if src.invert_percent else out


async def read_source(reader: SnmpReader, src: MetricSource) -> float | None:
    if src.mode == "scalar":
        return reduce_values(src, [await reader.get_optional(src.oid)])
    rows = await reader.walk(src.oid)
    return reduce_values(src, [v for _, v in rows])


def _pct(value: float | None) -> float | None:
    return round(value, 1) if value is not None and 0.0 <= value <= 100.0 else None


def memory_percent(used: float | None, free: float | None) -> float | None:
    if used is None or free is None or used < 0 or free < 0 or used + free <= 0:
        return None
    return _pct(used / (used + free) * 100)


async def read_cpu(reader: SnmpReader, profile: Profile) -> float | None:
    for src in profile.cpu:
        value = _pct(await read_source(reader, src))
        if value is not None:
            return value
    return None


async def read_memory_pct(reader: SnmpReader, profile: Profile) -> float | None:
    for spec in profile.memory:
        if spec.percent is not None:
            value = _pct(await read_source(reader, spec.percent))
        elif spec.used is not None and spec.free is not None:
            value = memory_percent(await read_source(reader, spec.used), await read_source(reader, spec.free))
        elif spec.total is not None and spec.available is not None:
            total, avail = await read_source(reader, spec.total), await read_source(reader, spec.available)
            value = None if total is None or avail is None or total <= 0 or avail > total \
                else memory_percent(total - avail, avail)
        else:
            value = None
        if value is not None:
            return value
    return None


async def read_temperature(reader: SnmpReader, profile: Profile) -> float | None:
    for src in profile.temperature:
        value = await read_source(reader, src)
        if value is not None and -50.0 <= value <= 200.0:  # outside = sensor garbage, not a temperature
            return round(value, 1)
    return None
