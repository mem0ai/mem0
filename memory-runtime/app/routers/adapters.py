from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.schemas.adapters import (
    AdapterEventCreate,
    AdapterEventRead,
    AdapterRecallRequest,
    AdapterRecallResponse,
)
from app.services.adapters import AdapterService

router = APIRouter(prefix="/adapters", tags=["adapters"])


def _ingest(adapter_name: str, payload: AdapterEventCreate, db: Session) -> AdapterEventRead:
    service = AdapterService(db)
    try:
        return service.ingest_event(adapter_name, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _recall(adapter_name: str, payload: AdapterRecallRequest, db: Session) -> AdapterRecallResponse:
    service = AdapterService(db)
    try:
        return service.recall(adapter_name, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/openclaw/events", response_model=AdapterEventRead, status_code=status.HTTP_201_CREATED)
def openclaw_event(payload: AdapterEventCreate, db: Session = Depends(get_db_session)) -> AdapterEventRead:
    return _ingest("openclaw", payload, db)


@router.post("/openclaw/recall", response_model=AdapterRecallResponse)
def openclaw_recall(payload: AdapterRecallRequest, db: Session = Depends(get_db_session)) -> AdapterRecallResponse:
    return _recall("openclaw", payload, db)


@router.post("/bunkerai/events", response_model=AdapterEventRead, status_code=status.HTTP_201_CREATED)
def bunkerai_event(payload: AdapterEventCreate, db: Session = Depends(get_db_session)) -> AdapterEventRead:
    return _ingest("bunkerai", payload, db)


@router.post("/bunkerai/recall", response_model=AdapterRecallResponse)
def bunkerai_recall(payload: AdapterRecallRequest, db: Session = Depends(get_db_session)) -> AdapterRecallResponse:
    return _recall("bunkerai", payload, db)
