import os
import json
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from src.graph import create_deep_agent_graph
from src.tools import read_workspace_file, list_workspace_files
from src.skills_manager import SkillsManager

load_dotenv()

# Ensure LangSmith Tracing is active
os.environ["LANGCHAIN_TRACING_V2"] = "true"

app = FastAPI(
    title="DeepAgent Medium Writer API",
    version="1.0.0",
    description="Production-grade API for Autonomous Pedagogical AI Article Generation"
)

# Enable CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Graph & Skills Manager
graph_app = create_deep_agent_graph(use_postgres=True)
skills_manager = SkillsManager(skills_dir="skills")

# In-Memory Session Store for Active Threads
threads_db: Dict[str, Dict[str, Any]] = {}


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class ArticleCreateRequest(BaseModel):
    topic: str = Field(..., example="LoRA & QLoRA Fine-Tuning Explained Visually")
    provider: Optional[str] = "openrouter"


class HITLFeedbackRequest(BaseModel):
    action: str = Field(..., example="approve") # "approve" or "revise"
    feedback: Optional[str] = Field(None, example="Add more details to Section 2.")


# ==========================================
# REST API ENDPOINTS (CRUD)
# ==========================================

@app.post("/api/articles", response_model=Dict[str, Any])
async def create_article_generation(req: ArticleCreateRequest):
    """[CREATE] Initiates a new AI Article Generation session."""
    import uuid
    thread_id = f"thread_{uuid.uuid4().hex[:10]}"
    
    threads_db[thread_id] = {
        "thread_id": thread_id,
        "topic": req.topic,
        "status": "processing",
        "current_step": "skill_router",
        "selected_redaction_skill": None,
        "selected_excalidraw_skill": None,
        "error": None
    }
    
    return {
        "message": "Generation job created successfully.",
        "thread_id": thread_id,
        "topic": req.topic
    }


@app.get("/api/articles", response_model=List[Dict[str, Any]])
async def list_article_generations():
    """[READ ALL] Lists all generation sessions and their statuses."""
    return list(threads_db.values())


@app.get("/api/articles/{thread_id}")
async def get_article_status(thread_id: str):
    """[READ ONE] Fetches current state and artifacts for a specific generation thread."""
    if thread_id not in threads_db:
        raise HTTPException(status_code=404, detail="Session thread not found.")
        
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = graph_app.get_state(config)
    
    thread_info = threads_db[thread_id]
    state_values = state_snapshot.values if state_snapshot else {}
    
    return {
        "session": thread_info,
        "state": {
            "topic": state_values.get("topic"),
            "selected_redaction_skill": state_values.get("selected_redaction_skill"),
            "selected_excalidraw_skill": state_values.get("selected_excalidraw_skill"),
            "next_node": state_values.get("next_node"),
            "research_notes_path": state_values.get("research_notes_path"),
            "draft_path": state_values.get("draft_path"),
            "diagrams_path": state_values.get("diagrams_path")
        },
        "next_step": state_snapshot.next if state_snapshot else []
    }


@app.get("/api/articles/{thread_id}/stream")
async def stream_article_generation(thread_id: str):
    """[REAL-TIME STREAMING] SSE Endpoint to track agent execution step-by-step."""
    if thread_id not in threads_db:
        raise HTTPException(status_code=404, detail="Session thread not found.")
        
    thread_info = threads_db[thread_id]
    config = {"configurable": {"thread_id": thread_id}}
    
    async def event_generator():
        initial_state = {
            "messages": [],
            "topic": thread_info["topic"],
            "selected_redaction_skill": None,
            "selected_excalidraw_skill": None,
            "research_notes_path": None,
            "draft_path": None,
            "diagrams_path": None,
            "next_node": "skill_router",
            "revision_feedback": None,
            "is_approved": False
        }
        
        try:
            # Stream execution
            for event in graph_app.stream(initial_state, config=config):
                for node_name, output in event.items():
                    thread_info["current_step"] = node_name
                    
                    if "selected_redaction_skill" in output:
                        thread_info["selected_redaction_skill"] = output["selected_redaction_skill"]
                    if "selected_excalidraw_skill" in output:
                        thread_info["selected_excalidraw_skill"] = output["selected_excalidraw_skill"]
                        
                    data = {
                        "node": node_name,
                        "thread_id": thread_id,
                        "output": {k: str(v) for k, v in output.items() if k != "messages"}
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    await asyncio.sleep(0.5)
                    
            # Check if paused for HITL
            state_snapshot = graph_app.get_state(config)
            if "human_review" in state_snapshot.next:
                thread_info["status"] = "waiting_human_review"
                yield f"data: {json.dumps({'event': 'HITL_INTERRUPT', 'status': 'waiting_human_review'})}\n\n"
            else:
                thread_info["status"] = "completed"
                yield f"data: {json.dumps({'event': 'COMPLETED', 'status': 'completed'})}\n\n"
                
        except Exception as e:
            thread_info["status"] = "failed"
            thread_info["error"] = str(e)
            yield f"data: {json.dumps({'event': 'ERROR', 'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/articles/{thread_id}/hitl")
async def submit_hitl_feedback(thread_id: str, req: HITLFeedbackRequest):
    """[UPDATE / HITL] Human-in-the-Loop Approval or Feedback Submission."""
    if thread_id not in threads_db:
        raise HTTPException(status_code=404, detail="Session thread not found.")
        
    config = {"configurable": {"thread_id": thread_id}}
    thread_info = threads_db[thread_id]
    
    if req.action == "approve":
        thread_info["status"] = "approved_completed"
        return {"message": "Article approved successfully!", "status": "approved_completed"}
        
    elif req.action == "revise":
        if not req.feedback:
            raise HTTPException(status_code=400, detail="Feedback is required for revision.")
            
        thread_info["status"] = "processing_revision"
        
        # Resume graph with feedback
        graph_app.update_state(config, {"revision_feedback": req.feedback, "draft_path": None})
        
        return {
            "message": "Revision feedback submitted. Re-run stream to view updates.",
            "status": "processing_revision",
            "feedback": req.feedback
        }


@app.get("/api/articles/{thread_id}/files/{filename}")
async def get_workspace_artifact(thread_id: str, filename: str):
    """[READ FILE] Fetches content of a workspace file (draft.md, research_notes.md, diagrams_spec.md)."""
    try:
        content = read_workspace_file.invoke({"filename": filename})
        return {"filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")


@app.delete("/api/articles/{thread_id}")
async def delete_article_session(thread_id: str):
    """[DELETE] Deletes a generation session from memory."""
    if thread_id in threads_db:
        del threads_db[thread_id]
        return {"message": f"Session {thread_id} deleted."}
    raise HTTPException(status_code=404, detail="Session not found.")


# Mount Static Files for Frontend
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_frontend():
    """Serves the main HTML Single-Page Application."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"message": "Frontend index.html not found. Place it in static/index.html."})