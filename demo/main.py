"""
Mem0 Demo Web Application
- Chat with LLM + Mem0 memory management
- Custom system prompt editor
- Skill system (Claude Agent Skills style)
- Admin page to inspect Mem0 memory context
"""

import os
import json
import uuid
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, AsyncIterator

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from mem0 import Memory

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── App Init ───────────────────────────────────────────────────────────────
app = FastAPI(title="Mem0 Demo", version="1.0.0")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

SKILLS_FILE = DATA_DIR / "skills.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ─── LLM Client ─────────────────────────────────────────────────────────────
llm_client = OpenAI(
    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
    api_key=os.getenv("LLM_API_KEY", "sk-placeholder"),
)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# ─── Mem0 Init ───────────────────────────────────────────────────────────────
mem0_config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": LLM_MODEL,
            "openai_base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            "api_key": os.getenv("LLM_API_KEY", "sk-placeholder"),
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            "openai_base_url": os.getenv(
                "EMBEDDING_BASE_URL", "https://api.openai.com/v1"
            ),
            "api_key": os.getenv("EMBEDDING_API_KEY", os.getenv("LLM_API_KEY", "sk-placeholder")),
        },
    },
    "vector_store": {
        "provider": "chroma",
        "config": {"path": str(DATA_DIR / "chroma_db")},
    },
    "history_db_path": str(DATA_DIR / "mem0_history.db"),
}

try:
    memory = Memory.from_config(mem0_config)
    logger.info("Mem0 initialized successfully")
except Exception as e:
    logger.error(f"Mem0 init failed: {e}")
    memory = None


# ─── Data Helpers ────────────────────────────────────────────────────────────
def load_skills() -> dict:
    if SKILLS_FILE.exists():
        return json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
    # Built-in default skills (mimicking Claude Agent Skills)
    defaults = {
        "translate": {
            "id": "translate",
            "name": "翻译助手",
            "description": "将文本翻译为指定语言",
            "prompt": "你是一个专业翻译，请将用户的内容翻译为目标语言。如果用户没有指定目标语言，默认翻译成英文。只输出翻译结果，不要解释。",
            "icon": "🌐",
            "created_at": datetime.now().isoformat(),
        },
        "summarize": {
            "id": "summarize",
            "name": "内容摘要",
            "description": "对长文本进行简洁摘要",
            "prompt": "你是一个文本摘要专家。请将用户提供的内容提炼成简洁的摘要，突出核心信息，控制在200字以内。",
            "icon": "📝",
            "created_at": datetime.now().isoformat(),
        },
        "code_review": {
            "id": "code_review",
            "name": "代码审查",
            "description": "审查代码质量并给出改进建议",
            "prompt": "你是一个资深软件工程师，专注于代码质量。请审查用户提供的代码，指出潜在问题、安全风险、性能优化点，并给出具体改进建议。",
            "icon": "🔍",
            "created_at": datetime.now().isoformat(),
        },
    }
    save_skills(defaults)
    return defaults


def save_skills(skills: dict):
    SKILLS_FILE.write_text(json.dumps(skills, ensure_ascii=False, indent=2), encoding="utf-8")


def load_sessions() -> dict:
    if SESSIONS_FILE.exists():
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    return {}


def save_sessions(sessions: dict):
    SESSIONS_FILE.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Pydantic Models ─────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None
    skill_id: Optional[str] = None
    use_memory: bool = True


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    memories_used: list
    memory_add_result: Optional[dict] = None


class SkillCreate(BaseModel):
    name: str
    description: str
    prompt: str
    icon: str = "🤖"


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    icon: Optional[str] = None


# ─── Routes: Pages ───────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/admin", response_class=HTMLResponse)
async def admin():
    return FileResponse(str(STATIC_DIR / "admin.html"))


# ─── Routes: Chat ────────────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    memories_used = []
    memory_add_result = None

    # 1. Retrieve relevant memories
    if req.use_memory and memory:
        try:
            search_result = memory.search(
                query=req.message,
                user_id=req.user_id,
                limit=5,
            )
            memories_used = search_result.get("results", [])
            logger.info(f"Retrieved {len(memories_used)} memories for user {req.user_id}")
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")

    # 2. Build system prompt
    skills = load_skills()
    base_system = req.system_prompt or "你是一个智能助手，请友好、准确地回答用户的问题。"

    # Apply skill override if specified
    if req.skill_id and req.skill_id in skills:
        skill = skills[req.skill_id]
        base_system = skill["prompt"]

    # Inject memory context
    if memories_used:
        memory_lines = "\n".join(
            f"- {m['memory']}" for m in memories_used
        )
        memory_block = f"\n\n【关于该用户的已知信息（来自记忆库）】\n{memory_lines}"
        base_system += memory_block

    # 3. Load session history
    sessions = load_sessions()
    session_history = sessions.get(session_id, [])

    # 4. Call LLM
    messages = [{"role": "system", "content": base_system}]
    messages.extend(session_history)
    messages.append({"role": "user", "content": req.message})

    try:
        response = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise HTTPException(status_code=502, detail=f"LLM call failed: {str(e)}")

    # 5. Save to session history
    session_history.append({"role": "user", "content": req.message})
    session_history.append({"role": "assistant", "content": reply})
    # Keep last 20 messages in session to avoid bloat
    sessions[session_id] = session_history[-20:]
    save_sessions(sessions)

    # 6. Add conversation to Mem0
    if req.use_memory and memory:
        try:
            mem_messages = [
                {"role": "user", "content": req.message},
                {"role": "assistant", "content": reply},
            ]
            memory_add_result = memory.add(mem_messages, user_id=req.user_id)
            logger.info(f"Memory add result: {memory_add_result}")
        except Exception as e:
            logger.warning(f"Memory add failed: {e}")

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        memories_used=memories_used,
        memory_add_result=memory_add_result,
    )


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, background_tasks: BackgroundTasks):
    """SSE streaming endpoint. Yields:
      data: {"type":"memories","data":[...]}
      data: {"type":"delta","text":"..."}
      data: {"type":"done","session_id":"...","mem_count":N}
      data: {"type":"error","message":"..."}
    """
    session_id = req.session_id or str(uuid.uuid4())

    # 1. Memory search (before streaming starts)
    memories_used = []
    if req.use_memory and memory:
        try:
            result = memory.search(query=req.message, user_id=req.user_id, limit=5)
            memories_used = result.get("results", [])
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")

    # 2. Build system prompt
    skills = load_skills()
    base_system = req.system_prompt or "你是一个智能助手，请友好、准确地回答用户的问题。"
    if req.skill_id and req.skill_id in skills:
        base_system = skills[req.skill_id]["prompt"]
    if memories_used:
        mem_lines = "\n".join(f"- {m['memory']}" for m in memories_used)
        base_system += f"\n\n【关于该用户的已知信息（来自记忆库）】\n{mem_lines}"

    # 3. Session history
    sessions = load_sessions()
    session_history = sessions.get(session_id, [])
    messages = [{"role": "system", "content": base_system}]
    messages.extend(session_history)
    messages.append({"role": "user", "content": req.message})

    async def event_generator() -> AsyncIterator[str]:
        # Send memories metadata first
        yield f"data: {json.dumps({'type': 'memories', 'data': memories_used}, ensure_ascii=False)}\n\n"

        full_reply = []
        full_thinking = []
        in_think_tag = False   # for <think>...</think> style models

        try:
            stream = await asyncio.to_thread(
                llm_client.chat.completions.create,
                model=LLM_MODEL,
                messages=messages,
                temperature=0.7,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # ── Thinking content (DeepSeek-R1 / QwQ style: reasoning_content field)
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    full_thinking.append(reasoning)
                    yield f"data: {json.dumps({'type': 'thinking_delta', 'text': reasoning}, ensure_ascii=False)}\n\n"

                # ── Regular content (may contain <think> tags for other models)
                content = delta.content or ""
                if not content:
                    continue

                # Handle <think>...</think> inline tag style
                while content:
                    if in_think_tag:
                        end = content.find("</think>")
                        if end == -1:
                            # Still inside <think>, forward as thinking
                            full_thinking.append(content)
                            yield f"data: {json.dumps({'type': 'thinking_delta', 'text': content}, ensure_ascii=False)}\n\n"
                            content = ""
                        else:
                            # End of think block
                            think_part = content[:end]
                            if think_part:
                                full_thinking.append(think_part)
                                yield f"data: {json.dumps({'type': 'thinking_delta', 'text': think_part}, ensure_ascii=False)}\n\n"
                            yield f"data: {json.dumps({'type': 'thinking_done'})}\n\n"
                            in_think_tag = False
                            content = content[end + len("</think>"):]
                    else:
                        start = content.find("<think>")
                        if start == -1:
                            # Normal content, no think tag
                            full_reply.append(content)
                            yield f"data: {json.dumps({'type': 'delta', 'text': content}, ensure_ascii=False)}\n\n"
                            content = ""
                        else:
                            # Normal content before <think>
                            before = content[:start]
                            if before:
                                full_reply.append(before)
                                yield f"data: {json.dumps({'type': 'delta', 'text': before}, ensure_ascii=False)}\n\n"
                            in_think_tag = True
                            content = content[start + len("<think>"):]

        except Exception as e:
            logger.error(f"LLM stream failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # Signal thinking complete if we got thinking content via reasoning_content field
        if full_thinking and not in_think_tag:
            yield f"data: {json.dumps({'type': 'thinking_done'})}\n\n"

        reply = "".join(full_reply)

        # Save session history
        session_history.append({"role": "user", "content": req.message})
        session_history.append({"role": "assistant", "content": reply})
        sessions[session_id] = session_history[-20:]
        save_sessions(sessions)

        # Add to Mem0 as background task
        if req.use_memory and memory and reply:
            def _mem_add():
                try:
                    mem_messages = [
                        {"role": "user", "content": req.message},
                        {"role": "assistant", "content": reply},
                    ]
                    result = memory.add(mem_messages, user_id=req.user_id)
                    added = [r for r in (result.get("results") or []) if r.get("event") != "NONE"]
                    logger.info(f"Mem0 add: {len(added)} memory updates for user {req.user_id}")
                except Exception as e:
                    logger.warning(f"Memory add failed: {e}")
            background_tasks.add_task(_mem_add)

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'mem_count': len(memories_used)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.delete("/api/chat/session/{session_id}")
async def clear_session(session_id: str):
    sessions = load_sessions()
    sessions.pop(session_id, None)
    save_sessions(sessions)
    return {"message": "Session cleared"}


# ─── Routes: Skills ──────────────────────────────────────────────────────────
@app.get("/api/skills")
async def list_skills():
    return load_skills()


@app.post("/api/skills")
async def create_skill(skill: SkillCreate):
    skills = load_skills()
    skill_id = str(uuid.uuid4())[:8]
    skills[skill_id] = {
        "id": skill_id,
        "name": skill.name,
        "description": skill.description,
        "prompt": skill.prompt,
        "icon": skill.icon,
        "created_at": datetime.now().isoformat(),
    }
    save_skills(skills)
    return skills[skill_id]


@app.put("/api/skills/{skill_id}")
async def update_skill(skill_id: str, skill: SkillUpdate):
    skills = load_skills()
    if skill_id not in skills:
        raise HTTPException(status_code=404, detail="Skill not found")
    for field, value in skill.model_dump(exclude_none=True).items():
        skills[skill_id][field] = value
    skills[skill_id]["updated_at"] = datetime.now().isoformat()
    save_skills(skills)
    return skills[skill_id]


@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str):
    skills = load_skills()
    if skill_id not in skills:
        raise HTTPException(status_code=404, detail="Skill not found")
    del skills[skill_id]
    save_skills(skills)
    return {"message": "Skill deleted"}


# ─── Routes: Admin / Memory ──────────────────────────────────────────────────
@app.get("/api/admin/memories")
async def get_all_memories(user_id: Optional[str] = None, limit: int = 100):
    if not memory:
        return {"results": [], "error": "Mem0 not initialized"}
    try:
        kwargs = {"limit": limit}
        if user_id:
            kwargs["user_id"] = user_id
        result = memory.get_all(**kwargs)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/memories/{memory_id}/history")
async def get_memory_history(memory_id: str):
    if not memory:
        raise HTTPException(status_code=503, detail="Mem0 not initialized")
    try:
        history = memory.history(memory_id)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/memories/{memory_id}")
async def delete_memory(memory_id: str):
    if not memory:
        raise HTTPException(status_code=503, detail="Mem0 not initialized")
    try:
        result = memory.delete(memory_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/memories")
async def delete_all_memories(user_id: Optional[str] = None):
    if not memory:
        raise HTTPException(status_code=503, detail="Mem0 not initialized")
    try:
        kwargs = {}
        if user_id:
            kwargs["user_id"] = user_id
        result = memory.delete_all(**kwargs)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/search")
async def search_memories(query: str, user_id: Optional[str] = None, limit: int = 10):
    if not memory:
        return {"results": []}
    try:
        kwargs = {"limit": limit}
        if user_id:
            kwargs["user_id"] = user_id
        result = memory.search(query=query, **kwargs)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/users")
async def list_users():
    """Scan memory to collect known user_ids."""
    if not memory:
        return {"users": []}
    try:
        all_mems = memory.get_all(limit=500)
        users = set()
        for m in all_mems.get("results", []):
            uid = m.get("user_id")
            if uid:
                users.add(uid)
        return {"users": sorted(users)}
    except Exception as e:
        return {"users": [], "error": str(e)}


# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", 8000)),
        reload=True,
    )
