import os
import json
import asyncio
import uuid
import redis.asyncio as aioredis
from typing import Optional, List, Dict, Any
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from src.tasks import generate_article_task, resume_article_task
from src.tools import read_workspace_file, list_workspace_files

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = FastAPI(
    title="DeepAgent Medium Writer API (Celery + Redis Edition)",
    version="2.0.0",
    description="Production API with Celery Tasks and Redis Pub/Sub Streaming"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class ArticleCreateRequest(BaseModel):
    topic: str = Field(..., example="LoRA & QLoRA Fine-Tuning Explained Visually")


class HITLFeedbackRequest(BaseModel):
    action: str = Field(..., example="approve") # "approve" or "revise"
    feedback: Optional[str] = Field(None, example="Add more details to Section 2.")


# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.post("/api/articles", response_model=Dict[str, Any])
async def create_article_generation(req: ArticleCreateRequest):
    """[CREATE] Dispatches a new Celery task to generate an article."""
    thread_id = f"thread_{uuid.uuid4().hex[:10]}"
    
    # Store initial status in Redis
    r = aioredis.from_url(REDIS_URL)
    await r.set(f"topic:{thread_id}", req.topic)
    await r.set(f"status:{thread_id}", "processing")
    
    # Dispatch Task to Celery Worker
    task = generate_article_task.delay(thread_id, req.topic)
    
    return {
        "message": "Celery task dispatched successfully.",
        "thread_id": thread_id,
        "task_id": task.id,
        "topic": req.topic
    }


@app.get("/api/articles/{thread_id}/stream")
async def stream_article_generation(thread_id: str):
    """[REAL-TIME STREAMING] Listens to Redis Pub/Sub and streams SSE to Frontend."""
    
    async def event_generator():
        r = aioredis.from_url(REDIS_URL)
        pubsub = r.pubsub()
        channel_name = f"channel:{thread_id}"
        await pubsub.subscribe(channel_name)
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data_str = message["data"].decode("utf-8")
                    yield f"data: {data_str}\n\n"
                    
                    data_json = json.loads(data_str)
                    if data_json.get("event") in ["COMPLETED", "HITL_INTERRUPT", "ERROR"]:
                        break
        finally:
            await pubsub.unsubscribe(channel_name)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/articles/{thread_id}/hitl")
async def submit_hitl_feedback(thread_id: str, req: HITLFeedbackRequest):
    """[HITL] Submits Human approval or triggers a Celery revision task."""
    r = aioredis.from_url(REDIS_URL)
    
    if req.action == "approve":
        await r.set(f"status:{thread_id}", "approved_completed")
        return {"message": "Article approved successfully!", "status": "approved_completed"}
        
    elif req.action == "revise":
        if not req.feedback:
            raise HTTPException(status_code=400, detail="Feedback is required for revision.")
            
        await r.set(f"status:{thread_id}", "processing_revision")
        # Dispatch Revision Task to Celery Worker
        task = resume_article_task.delay(thread_id, req.feedback)
        
        return {
            "message": "Revision task dispatched to Celery.",
            "task_id": task.id,
            "status": "processing_revision"
        }


@app.get("/api/articles/{thread_id}/files/{filename}")
async def get_workspace_artifact(thread_id: str, filename: str):
    """Fetches content of workspace files."""
    try:
        content = read_workspace_file.invoke({"filename": filename})
        return {"filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")


# Mount Static Files
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_frontend():
    return FileResponse(static_dir / "index.html")