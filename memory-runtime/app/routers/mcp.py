from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.services.mcp import MCPService

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.post("/{client_name}/http/{user_id}")
async def streamable_http_mcp(
    client_name: str,
    user_id: str,
    request: Request,
    db: Session = Depends(get_db_session),
) -> JSONResponse:
    accept = request.headers.get("accept", "")
    if "application/json" not in accept:
        raise HTTPException(status_code=406, detail="MCP requires Accept: application/json")

    content_type = request.headers.get("content-type", "")
    if content_type and "application/json" not in content_type:
        raise HTTPException(status_code=415, detail="MCP requires Content-Type: application/json")

    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON-RPC payload must be an object")

    response = MCPService(db).handle_request(
        payload=payload,
        client_name=client_name,
        user_id=user_id,
    )
    return JSONResponse(response)


@router.delete("/{client_name}/http/{user_id}")
async def delete_streamable_http_session(client_name: str, user_id: str) -> None:
    raise HTTPException(status_code=405, detail="Stateless MCP transport does not keep sessions")
