import os
import json
from typing import Dict, Any, Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

# Imports officiels langgraph-checkpoint-postgres
try:
    from langgraph.checkpoint.postgres import PostgresSaver
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

from src.config import LLMFactory
from src.skills_manager import SkillsManager
from src.state import DeepAgentState
from src.agents import excalidraw_merger_node, researcher_node, writer_node, excalidraw_node
from src.prompts import (
    SKILL_ROUTER_SYSTEM_PROMPT,
    SUPERVISOR_ROUTER_PROMPT
)

skills_manager = SkillsManager(skills_dir="skills")


# ==========================================
# 1. SKILL ROUTER NODE
# ==========================================
def skill_router_node(state: DeepAgentState) -> Dict[str, Any]:
    topic = state["topic"]
    print(f"\n🧠 [Skill Router] Analyzing topic: '{topic}'...")

    skills_index = skills_manager.get_skills_index_for_prompt()
    sys_prompt = SKILL_ROUTER_SYSTEM_PROMPT.format(topic=topic, skills_index=skills_index)

    llm = LLMFactory.get_model(provider=os.getenv("PROVIDER"), temperature=0.1)
    response = llm.invoke([
        SystemMessage(content=sys_prompt),
        HumanMessage(content=f"Select optimal skills for: '{topic}'")
    ])

    try:
        clean_content = response.content.replace("```json", "").replace("```", "").strip()
        selection = json.loads(clean_content)
        return {
            "selected_redaction_skill": selection.get("selected_redaction_skill"),
            "selected_excalidraw_skill": selection.get("selected_excalidraw_skill"),
            "skill_selection_rationale": selection.get("rationale"),
            "next_node": "supervisor"
        }
    except Exception:
        return {
            "selected_redaction_skill": "redaction-feynman-deep-dive",
            "selected_excalidraw_skill": "excalidraw-pipeline-flow",
            "skill_selection_rationale": "Fallback default skills.",
            "next_node": "supervisor"
        }


# ==========================================
# 2. SUPERVISOR NODE
# ==========================================
# (Dans src/graph.py)
def supervisor_node(state: DeepAgentState) -> Dict[str, Any]:
    topic = state["topic"]
    research_path = state.get("research_notes_path") or "workspace/research_notes.md"
    draft_path = state.get("draft_path") or "workspace/draft.md"
    diagrams_path = state.get("diagrams_path") or "workspace/diagrams_spec.md"
    final_path = state.get("final_article_path") or "workspace/final_article.md"
    feedback = state.get("revision_feedback")

    print(f"\n👑 [Supervisor Agent] Evaluating workspace artifacts...")

    if feedback:
        print(f"   ⚠️ Revision Feedback received: '{feedback}'")
        if os.path.exists(final_path): os.remove(final_path)
        if os.path.exists(draft_path): os.remove(draft_path)
        return {"draft_path": None, "final_article_path": None, "revision_feedback": None, "next_node": "writer"}

    # Routage Déterministe
    if not os.path.exists(research_path):
        next_node = "researcher"
    elif not os.path.exists(draft_path):
        next_node = "writer"
    elif not os.path.exists(diagrams_path):
        next_node = "excalidraw"
    elif not os.path.exists(final_path):
        next_node = "excalidraw_merger"
    else:
        next_node = "human_review"

    print(f"   👉 Supervisor Routing Decision -> '{next_node}'")
    return {"next_node": next_node}


# ==========================================
# 3. HUMAN REVIEW NODE (HITL Interrupt Point)
# ==========================================
def human_review_node(state: DeepAgentState) -> Dict[str, Any]:
    """
    Node acting as the pause point for Human-in-the-Loop review.
    """
    print(f"\n⏸️ [Human Review Node] Pipeline paused. Ready for Human-in-the-Loop approval.")
    return {"next_node": "human_review"}


def route_next_step(state: DeepAgentState) -> Literal["researcher", "writer", "excalidraw", "human_review"]:
    return state.get("next_node", "human_review")


# ==========================================
# 4. COMPILER WITH POSTGRES CHECKPOINTER
# ==========================================
def create_deep_agent_graph(use_postgres: bool = True):
    builder = StateGraph(DeepAgentState)

    builder.add_node("skill_router", skill_router_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("writer", writer_node)
    builder.add_node("excalidraw", excalidraw_node)
    builder.add_node("excalidraw_merger", excalidraw_merger_node)
    builder.add_node("human_review", human_review_node)

    builder.add_edge(START, "skill_router")
    builder.add_edge("skill_router", "supervisor")

    builder.add_conditional_edges(
        "supervisor",
        route_next_step,
        {
            "researcher": "researcher",
            "writer": "writer",
            "excalidraw": "excalidraw",
            "excalidraw_merger": "excalidraw_merger",
            "human_review": "human_review"
        }
    )

    builder.add_edge("researcher", "supervisor")
    builder.add_edge("writer", "supervisor")
    builder.add_edge("excalidraw", "supervisor")
    builder.add_edge("excalidraw_merger", "supervisor")
    builder.add_edge("human_review", END)

    # Checkpointer configuration ...
    db_uri = os.getenv("POSTGRES_DB_URI")
    checkpointer = None
    if use_postgres and POSTGRES_AVAILABLE and db_uri:
        try:
            pool = ConnectionPool(conninfo=db_uri, max_size=20, kwargs={"autocommit": True, "row_factory": dict_row})
            checkpointer = PostgresSaver(pool)
            checkpointer.setup()
        except Exception:
            checkpointer = MemorySaver()
    else:
        checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer, interrupt_before=["human_review"])
