"""Dashboard API — spending aggregates derived solely from saved records (US8)."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.services import dashboard_service
from src.services.auth import require_user
from src.services.persistence import PersistenceError

logger = logging.getLogger("billology.dashboard")
router = APIRouter(tags=["dashboard"], dependencies=[Depends(require_user)])


@router.get("/dashboard/by-category")
def dashboard_by_category(date_from: Optional[str] = None, date_to: Optional[str] = None):
    try:
        return dashboard_service.by_category(date_from=date_from, date_to=date_to)
    except PersistenceError as exc:
        logger.error("dashboard by-category failed: %s", exc)
        return JSONResponse(
            status_code=502, content={"error": "persist_failed", "detail": str(exc)}
        )


@router.get("/dashboard/monthly")
def dashboard_monthly(date_from: Optional[str] = None, date_to: Optional[str] = None):
    try:
        return dashboard_service.monthly(date_from=date_from, date_to=date_to)
    except PersistenceError as exc:
        logger.error("dashboard monthly failed: %s", exc)
        return JSONResponse(
            status_code=502, content={"error": "persist_failed", "detail": str(exc)}
        )
