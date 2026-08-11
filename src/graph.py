import json
from typing import Dict, Any, Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

from config import LLMFactory
from skills_manager import SkillsManager
from state import DeepAgentState
from agents import researcher_node, writer_node, excalidraw_node
from prompts import (
    SKILL_ROUTER_SYSTEM_PROMPT,
    SUPERVISOR_ROUTER_PROMPT
)
import os

# Global instances
skills_manager = SkillsManager(skills_dir="skills")


# ==========================================
# 1. SKILL ROUTER NODE
# ==========================================
def skill_router_node(state: DeepAgentState) -> Dict[str, Any]:
    """
    Evaluates the article topic and dynamically selects the best Redaction and Excalidraw Skills.
    """
    topic = state["topic"]
    print(f"\n🧠 [Skill Router] Analyzing topic: '{topic}'...")

    # Get index of all available skills
    skills_index = skills_manager.get_skills_index_for_prompt()

    sys_prompt = SKILL_ROUTER_SYSTEM_PROMPT.format(
        topic=topic,
        skills_index=skills_index
    )

    llm = LLMFactory.get_model(
        provider=os.getenv("PROVIDER"),
        temperature=0.1
    )

    response = llm.invoke([
        SystemMessage(content=sys_prompt),
        HumanMessage(content=f"Select the optimal skills for topic: '{topic}'")
    ])

    try:
        # Clean JSON markdown fences if present
        clean_content = response.content.replace("```json", "").replace("```", "").strip()
        selection = json.loads(clean_content)

        redaction_skill = selection.get("selected_redaction_skill")
        excalidraw_skill = selection.get("selected_excalidraw_skill")
        rationale = selection.get("rationale", "Optimal skill selection based on topic requirements.")

        print(f"   🎯 Selected Redaction Skill : {redaction_skill}")
        print(f"   🎨 Selected Excalidraw Skill: {excalidraw_skill}")
        print(f"   💡 Rationale: {rationale}")

        return {
            "selected_redaction_skill": redaction_skill,
            "selected_excalidraw_skill": excalidraw_skill,
            "skill_selection_rationale": rationale,
            "next_node": "supervisor"
        }

    except Exception as e:
        print(f"⚠️ Failed to parse Skill Router JSON, using fallback skills. Error: {e}")
        return {
            "selected_redaction_skill": "redaction-feynman-deep-dive",
            "selected_excalidraw_skill": "excalidraw-pipeline-flow",
            "skill_selection_rationale": "Fallback default skills.",
            "next_node": "supervisor"
        }


# ==========================================
# 2. SUPERVISOR NODE
# ==========================================
def supervisor_node(state: DeepAgentState) -> Dict[str, Any]:
    """
    Orchestrates execution flow by checking artifact status and routing to the appropriate agent.
    """
    topic = state["topic"]
    research_status = state.get("research_notes_path")
    draft_status = state.get("draft_path")
    diagrams_status = state.get("diagrams_path")

    print(f"\n👑 [Supervisor Agent] Evaluating artifact status...")
    print(f"   - Research Notes: {research_status}")
    print(f"   - Draft Article : {draft_status}")
    print(f"   - Diagrams Spec : {diagrams_status}")

    sys_prompt = SUPERVISOR_ROUTER_PROMPT.format(
        topic=topic,
        research_notes_status=research_status,
        draft_status=draft_status,
        diagrams_status=diagrams_status
    )

    llm = LLMFactory.get_model(
        provider=os.getenv("PROVIDER"),
        temperature=0.0
    )

    response = llm.invoke([
        SystemMessage(content=sys_prompt),
        HumanMessage(content="Determine the next node to execute.")
    ])

    try:
        clean_content = response.content.replace("```json", "").replace("```", "").strip()
        decision = json.loads(clean_content)
        next_node = decision.get("next_node", "human_review")
        print(f"   👉 Supervisor Routing Decision -> '{next_node}' ({decision.get('rationale')})")
        return {"next_node": next_node}
    except Exception as e:
        print(f"⚠️ Supervisor fallback routing due to error: {e}")
        return {"next_node": "human_review"}


# ==========================================
# 3. ROUTING FUNCTION FOR CONDITIONAL EDGES
# ==========================================
def route_next_step(state: DeepAgentState) -> Literal["researcher", "writer", "excalidraw", "human_review"]:
    """
    Conditional edge router reading state['next_node'].
    """
    next_node = state.get("next_node", "human_review")
    if next_node in ["researcher", "writer", "excalidraw", "human_review"]:
        return next_node
    return "human_review"


# ==========================================
# 4. LANGGRAPH ASSEMBLY
# ==========================================
def create_deep_agent_graph():
    """
    Assembles the complete DeepAgent StateGraph.
    """
    builder = StateGraph(DeepAgentState)

    # Add Nodes
    builder.add_node("skill_router", skill_router_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("writer", writer_node)
    builder.add_node("excalidraw", excalidraw_node)

    # Add Edges
    builder.add_edge(START, "skill_router")
    builder.add_edge("skill_router", "supervisor")

    # Conditional routing from Supervisor
    builder.add_conditional_edges(
        "supervisor",
        route_next_step,
        {
            "researcher": "researcher",
            "writer": "writer",
            "excalidraw": "excalidraw",
            "human_review": END  # Will be hooked to HITL in Step 6
        }
    )

    # Sub-agents loop back to Supervisor after completing their task
    builder.add_edge("researcher", "supervisor")
    builder.add_edge("writer", "supervisor")
    builder.add_edge("excalidraw", "supervisor")

    return builder.compile()


# ==========================================
# 🧪 TEST GRAPH COMPILATION
# ==========================================
if __name__ == "__main__":
    print("🧪 Testing LangGraph StateGraph Assembly...")
    
    app = create_deep_agent_graph()
    print("✅ LangGraph compiled successfully!")
    print(f"   Nodes in graph: {list(app.nodes.keys())}")