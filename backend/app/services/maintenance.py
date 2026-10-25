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
        log.warning("app.services.maintenance is a STUB — status not updated")

async def set_observed_status(db: Any, device: Any, status: str) -> Any:
    _w(); return None
