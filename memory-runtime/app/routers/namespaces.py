from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.schemas.namespace import (
    AgentCreate,
    AgentRead,
    NamespaceCreate,
    NamespaceRead,
)
from app.services.namespaces import NamespaceService

router = APIRouter(prefix="/namespaces", tags=["namespaces"])


@router.post("", response_model=NamespaceRead, status_code=status.HTTP_201_CREATED)
def create_namespace(payload: NamespaceCreate, db: Session = Depends(get_db_session)) -> NamespaceRead:
    service = NamespaceService(db)
    try:
        return service.create_namespace(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{namespace_id}", response_model=NamespaceRead)
def get_namespace(namespace_id: str, db: Session = Depends(get_db_session)) -> NamespaceRead:
    service = NamespaceService(db)
    namespace = service.get_namespace(namespace_id)
    if namespace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Namespace not found")
    return namespace


@router.post("/{namespace_id}/agents", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
def create_agent(namespace_id: str, payload: AgentCreate, db: Session = Depends(get_db_session)) -> AgentRead:
    service = NamespaceService(db)
    try:
        return service.create_agent(namespace_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
