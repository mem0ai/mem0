from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.schemas.adapters import (
    AdapterBootstrapRequest,
    AdapterBootstrapResponse,
    AdapterEventCreate,
    AdapterEventRead,
    AdapterMemoryRead,
    AdapterMemorySearchRequest,
    AdapterMemorySearchResponse,
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


def _bootstrap(adapter_name: str, payload: AdapterBootstrapRequest, db: Session) -> AdapterBootstrapResponse:
    service = AdapterService(db)
    try:
        return service.bootstrap(adapter_name, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _search(adapter_name: str, payload: AdapterMemorySearchRequest, db: Session) -> AdapterMemorySearchResponse:
    service = AdapterService(db)
    try:
        return service.search_memories(adapter_name, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/openclaw/events", response_model=AdapterEventRead, status_code=status.HTTP_201_CREATED)
def openclaw_event(payload: AdapterEventCreate, db: Session = Depends(get_db_session)) -> AdapterEventRead:
    return _ingest("openclaw", payload, db)


@router.post("/openclaw/bootstrap", response_model=AdapterBootstrapResponse)
def openclaw_bootstrap(payload: AdapterBootstrapRequest, db: Session = Depends(get_db_session)) -> AdapterBootstrapResponse:
    return _bootstrap("openclaw", payload, db)


@router.post("/openclaw/recall", response_model=AdapterRecallResponse)
def openclaw_recall(payload: AdapterRecallRequest, db: Session = Depends(get_db_session)) -> AdapterRecallResponse:
    return _recall("openclaw", payload, db)


@router.post("/openclaw/search", response_model=AdapterMemorySearchResponse)
def openclaw_search(payload: AdapterMemorySearchRequest, db: Session = Depends(get_db_session)) -> AdapterMemorySearchResponse:
    return _search("openclaw", payload, db)


@router.get("/openclaw/memories", response_model=AdapterMemorySearchResponse)
def openclaw_list_memories(
    namespace_id: str = Query(...),
    agent_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
) -> AdapterMemorySearchResponse:
    service = AdapterService(db)
    try:
        return service.list_memories(
            adapter_name="openclaw",
            namespace_id=namespace_id,
            agent_id=agent_id,
            session_id=session_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/openclaw/memories/{memory_id}", response_model=AdapterMemoryRead)
def openclaw_get_memory(
    memory_id: str,
    namespace_id: str = Query(...),
    agent_id: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
) -> AdapterMemoryRead:
    service = AdapterService(db)
    try:
        return service.get_memory(
            adapter_name="openclaw",
            namespace_id=namespace_id,
            agent_id=agent_id,
            memory_id=memory_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/openclaw/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def openclaw_delete_memory(
    memory_id: str,
    namespace_id: str = Query(...),
    agent_id: str | None = Query(default=None),
    db: Session = Depends(get_db_session),
) -> None:
    service = AdapterService(db)
    try:
        service.delete_memory(
            adapter_name="openclaw",
            namespace_id=namespace_id,
            agent_id=agent_id,
            memory_id=memory_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/bunkerai/events", response_model=AdapterEventRead, status_code=status.HTTP_201_CREATED)
def bunkerai_event(payload: AdapterEventCreate, db: Session = Depends(get_db_session)) -> AdapterEventRead:
    return _ingest("bunkerai", payload, db)


@router.post("/bunkerai/recall", response_model=AdapterRecallResponse)
def bunkerai_recall(payload: AdapterRecallRequest, db: Session = Depends(get_db_session)) -> AdapterRecallResponse:
    return _recall("bunkerai", payload, db)
