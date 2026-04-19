from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.schemas.recall import RecallRequest, RecallResponse
from app.services.retrieval import RetrievalService

router = APIRouter(prefix="/recall", tags=["recall"])


@router.post("", response_model=RecallResponse)
def recall(payload: RecallRequest, db: Session = Depends(get_db_session)) -> RecallResponse:
    service = RetrievalService(db)
    try:
        return service.recall(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
