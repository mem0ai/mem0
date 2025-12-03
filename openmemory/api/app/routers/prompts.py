from typing import List, Optional
from datetime import datetime
from uuid import UUID

from app.database import get_db
from app.models import Prompt, PromptType
from app.utils.memory import reset_memory_client
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


class PromptSchema(BaseModel):
    """Schema for Prompt response"""
    id: str
    prompt_type: str
    display_name: str
    description: Optional[str] = None
    content: str
    is_active: bool
    version: int
    metadata_: dict = {}
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PromptCreateSchema(BaseModel):
    """Schema for creating a new prompt"""
    prompt_type: str = Field(..., description="Type of the prompt")
    display_name: str = Field(..., description="Human-readable name")
    description: Optional[str] = Field(None, description="Description of the prompt")
    content: str = Field(..., description="The actual prompt content")
    is_active: bool = Field(True, description="Whether this prompt is active")
    metadata_: dict = Field(default_factory=dict, description="Additional metadata")


class PromptUpdateSchema(BaseModel):
    """Schema for updating an existing prompt"""
    display_name: Optional[str] = Field(None, description="Human-readable name")
    description: Optional[str] = Field(None, description="Description of the prompt")
    content: Optional[str] = Field(None, description="The actual prompt content")
    is_active: Optional[bool] = Field(None, description="Whether this prompt is active")
    metadata_: Optional[dict] = Field(None, description="Additional metadata")


@router.get("/", response_model=List[PromptSchema])
async def list_prompts(
    prompt_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List all prompts with optional filtering."""
    import logging
    logging.info(f"[PROMPTS] Listing prompts - prompt_type={prompt_type}, is_active={is_active}")

    query = db.query(Prompt)

    if prompt_type:
        query = query.filter(Prompt.prompt_type == prompt_type)

    if is_active is not None:
        query = query.filter(Prompt.is_active == is_active)

    prompts = query.order_by(Prompt.created_at.desc()).all()
    logging.info(f"[PROMPTS] Found {len(prompts)} prompts in database")

    # Convert to dict
    result = []
    for prompt in prompts:
        prompt_dict = {
            "id": str(prompt.id),
            "prompt_type": prompt.prompt_type,
            "display_name": prompt.display_name,
            "description": prompt.description,
            "content": prompt.content,
            "is_active": prompt.is_active,
            "version": prompt.version,
            "metadata_": prompt.metadata_ or {},
            "created_at": prompt.created_at,
            "updated_at": prompt.updated_at,
        }
        result.append(prompt_dict)

    return result


@router.get("/types")
async def list_prompt_types():
    """List all available prompt types."""
    return {
        "prompt_types": [
            {
                "value": pt.value,
                "name": pt.name.replace("_", " ").title()
            }
            for pt in PromptType
        ]
    }


@router.post("/", response_model=PromptSchema)
async def create_prompt(
    prompt_create: PromptCreateSchema,
    db: Session = Depends(get_db)
):
    """Create a new prompt."""
    try:
        new_prompt = Prompt(
            prompt_type=prompt_create.prompt_type,
            display_name=prompt_create.display_name,
            description=prompt_create.description,
            content=prompt_create.content,
            is_active=prompt_create.is_active,
            version=1,
            metadata_=prompt_create.metadata_ or {},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        db.add(new_prompt)
        db.commit()
        db.refresh(new_prompt)

        # Reset memory client if this is an active prompt
        if new_prompt.is_active:
            reset_memory_client()

        return {
            "id": str(new_prompt.id),
            "prompt_type": new_prompt.prompt_type,
            "display_name": new_prompt.display_name,
            "description": new_prompt.description,
            "content": new_prompt.content,
            "is_active": new_prompt.is_active,
            "version": new_prompt.version,
            "metadata_": new_prompt.metadata_ or {},
            "created_at": new_prompt.created_at,
            "updated_at": new_prompt.updated_at,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create prompt: {str(e)}")


@router.get("/{prompt_id}", response_model=PromptSchema)
async def get_prompt_by_id(prompt_id: str, db: Session = Depends(get_db)):
    """Get a specific prompt by ID."""
    try:
        uuid_id = UUID(prompt_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {prompt_id}")

    prompt = db.query(Prompt).filter(Prompt.id == uuid_id).first()

    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    return {
        "id": str(prompt.id),
        "prompt_type": prompt.prompt_type,
        "display_name": prompt.display_name,
        "description": prompt.description,
        "content": prompt.content,
        "is_active": prompt.is_active,
        "version": prompt.version,
        "metadata_": prompt.metadata_ or {},
        "created_at": prompt.created_at,
        "updated_at": prompt.updated_at,
    }


@router.get("/type/{prompt_type}", response_model=List[PromptSchema])
async def get_prompts_by_type(prompt_type: str, db: Session = Depends(get_db)):
    """Get all prompts of a specific type."""
    prompts = db.query(Prompt).filter(
        Prompt.prompt_type == prompt_type
    ).order_by(Prompt.version.desc()).all()

    if not prompts:
        raise HTTPException(status_code=404, detail=f"No prompts found for type: {prompt_type}")

    result = []
    for prompt in prompts:
        result.append({
            "id": str(prompt.id),
            "prompt_type": prompt.prompt_type,
            "display_name": prompt.display_name,
            "description": prompt.description,
            "content": prompt.content,
            "is_active": prompt.is_active,
            "version": prompt.version,
            "metadata_": prompt.metadata_ or {},
            "created_at": prompt.created_at,
            "updated_at": prompt.updated_at,
        })

    return result


@router.put("/{prompt_id}", response_model=PromptSchema)
async def update_prompt(
    prompt_id: str,
    prompt_update: PromptUpdateSchema,
    db: Session = Depends(get_db)
):
    """Update an existing prompt."""
    try:
        uuid_id = UUID(prompt_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {prompt_id}")

    prompt = db.query(Prompt).filter(Prompt.id == uuid_id).first()

    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    # Update fields if provided
    update_data = prompt_update.dict(exclude_unset=True)

    # If content is being updated, increment version
    if "content" in update_data and update_data["content"] != prompt.content:
        prompt.version += 1

    for field, value in update_data.items():
        setattr(prompt, field, value)

    prompt.updated_at = datetime.now()

    db.commit()
    db.refresh(prompt)

    # Reset memory client to pick up new prompts
    reset_memory_client()

    return {
        "id": str(prompt.id),
        "prompt_type": prompt.prompt_type,
        "display_name": prompt.display_name,
        "description": prompt.description,
        "content": prompt.content,
        "is_active": prompt.is_active,
        "version": prompt.version,
        "metadata_": prompt.metadata_ or {},
        "created_at": prompt.created_at,
        "updated_at": prompt.updated_at,
    }


@router.delete("/{prompt_id}", response_model=dict)
async def delete_prompt(prompt_id: str, db: Session = Depends(get_db)):
    """Delete a prompt."""
    try:
        uuid_id = UUID(prompt_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {prompt_id}")

    prompt = db.query(Prompt).filter(Prompt.id == uuid_id).first()

    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    prompt_type = prompt.prompt_type
    db.delete(prompt)
    db.commit()

    # Reset memory client if this was an active prompt
    reset_memory_client()

    return {"message": f"Prompt '{prompt_type}' deleted successfully"}


@router.post("/{prompt_id}/reset", response_model=PromptSchema)
async def reset_prompt_to_default(prompt_id: str, db: Session = Depends(get_db)):
    """Reset a prompt to its default value."""
    try:
        uuid_id = UUID(prompt_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {prompt_id}")

    prompt = db.query(Prompt).filter(Prompt.id == uuid_id).first()

    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    prompt_type = prompt.prompt_type

    # Get default prompts from the prompts module
    from app.utils.prompts import (
        FACT_RETRIEVAL_PROMPT,
        USER_MEMORY_EXTRACTION_PROMPT,
        AGENT_MEMORY_EXTRACTION_PROMPT,
        DEFAULT_UPDATE_MEMORY_PROMPT,
        MEMORY_ANSWER_PROMPT,
        MEMORY_CATEGORIZATION_PROMPT,
        PROCEDURAL_MEMORY_SYSTEM_PROMPT
    )

    default_prompts = {
        "fact_retrieval": {
            "content": FACT_RETRIEVAL_PROMPT,
            "display_name": "Fact Retrieval",
            "description": "Extract relevant facts from conversations"
        },
        "user_memory_extraction": {
            "content": USER_MEMORY_EXTRACTION_PROMPT,
            "display_name": "User Memory Extraction",
            "description": "Extract user-specific memories and preferences from conversations"
        },
        "agent_memory_extraction": {
            "content": AGENT_MEMORY_EXTRACTION_PROMPT,
            "display_name": "Agent Memory Extraction",
            "description": "Extract agent/assistant-specific memories and characteristics"
        },
        "update_memory": {
            "content": DEFAULT_UPDATE_MEMORY_PROMPT,
            "display_name": "Update Memory",
            "description": "Manage memory operations (add, update, delete, no change)"
        },
        "memory_answer": {
            "content": MEMORY_ANSWER_PROMPT,
            "display_name": "Memory Answer",
            "description": "Answer questions based on stored memories"
        },
        "memory_categorization": {
            "content": MEMORY_CATEGORIZATION_PROMPT,
            "display_name": "Memory Categorization",
            "description": "Categorize memories into predefined or custom categories"
        },
        "procedural_memory": {
            "content": PROCEDURAL_MEMORY_SYSTEM_PROMPT,
            "display_name": "Procedural Memory",
            "description": "Summarize procedural execution history"
        }
    }

    if prompt_type not in default_prompts:
        raise HTTPException(status_code=400, detail=f"No default prompt available for: {prompt_type}")

    # Reset to default
    default = default_prompts[prompt_type]
    prompt.content = default["content"]
    prompt.display_name = default["display_name"]
    prompt.description = default["description"]
    prompt.version += 1
    prompt.updated_at = datetime.now()

    db.commit()
    db.refresh(prompt)

    # Reset memory client to pick up new prompts
    reset_memory_client()

    return {
        "id": str(prompt.id),
        "prompt_type": prompt.prompt_type,
        "display_name": prompt.display_name,
        "description": prompt.description,
        "content": prompt.content,
        "is_active": prompt.is_active,
        "version": prompt.version,
        "metadata_": prompt.metadata_ or {},
        "created_at": prompt.created_at,
        "updated_at": prompt.updated_at,
    }


@router.patch("/{prompt_id}/toggle", response_model=PromptSchema)
async def toggle_prompt(prompt_id: str, db: Session = Depends(get_db)):
    """Toggle the active status of a prompt."""
    try:
        uuid_id = UUID(prompt_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {prompt_id}")

    prompt = db.query(Prompt).filter(Prompt.id == uuid_id).first()

    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {prompt_id}")

    prompt.is_active = not prompt.is_active
    prompt.updated_at = datetime.now()

    db.commit()
    db.refresh(prompt)

    # Reset memory client to pick up new prompts
    reset_memory_client()

    return {
        "id": str(prompt.id),
        "prompt_type": prompt.prompt_type,
        "display_name": prompt.display_name,
        "description": prompt.description,
        "content": prompt.content,
        "is_active": prompt.is_active,
        "version": prompt.version,
        "metadata_": prompt.metadata_ or {},
        "created_at": prompt.created_at,
        "updated_at": prompt.updated_at,
    }
