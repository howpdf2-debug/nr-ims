"""Phase 2 stub — Account 1 owns the real implementation."""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)
_W = False

def _w() -> None:
    global _W
    if not _W:
        _W = True
        log.warning("app.services.alarms is a STUB — dead-man alarms not persisted")

async def raise_alarm(db: Any, *, device: Any, external_id: str, severity: str, message: str) -> Any:
    _w()
    return None

async def resolve_alarm(db: Any, alarm: Any, *, resolved_by: str, note: str) -> Any:
    _w()
    return None
