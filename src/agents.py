from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
import os

from config import LLMFactory
from skills_manager import SkillsManager
from state import DeepAgentState
from tools import (
    ALL_TOOLS,
    web_search_tavily,
    execute_python_sandbox,
    write_workspace_file,
    read_workspace_file,
    load_skill_instruction
)
from prompts import (
    RESEARCHER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
    EXCALIDRAW_SYSTEM_PROMPT
)

# Global instances
skills_manager = SkillsManager(skills_dir="skills")


# ==========================================
# 1. DEEP RESEARCHER NODE
# ==========================================
def researcher_node(state: DeepAgentState) -> Dict[str, Any]:
    """
    Sub-Agent responsible for web search, running code tests, and generating workspace/research_notes.md.
    """
    topic = state["topic"]
    print(f"\n🔍 [Researcher Agent] Starting deep research on: '{topic}'")

    # Instantiate LLM with Tools
    llm = LLMFactory.get_model(provider=os.getenv("PROVIDER"), temperature=0.2)
    llm_with_tools = llm.bind_tools([web_search_tavily, execute_python_sandbox, write_workspace_file, read_workspace_file])

    sys_prompt = RESEARCHER_SYSTEM_PROMPT.format(topic=topic)
    
    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=f"Perform research, run code verification if needed, and write research_notes.md for topic: {topic}")
    ]

    # Execute Agent step with Tool Loop
    response = llm_with_tools.invoke(messages)
    
    # Handle Tool calls if any
    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            print(f"   🛠️ [Researcher Tool Call] {tool_name}({tool_args})")
            
            if tool_name == "web_search_tavily":
                res = web_search_tavily.invoke(tool_args)
            elif tool_name == "execute_python_sandbox":
                res = execute_python_sandbox.invoke(tool_args)
            elif tool_name == "write_workspace_file":
                res = write_workspace_file.invoke(tool_args)
            elif tool_name == "read_workspace_file":
                res = read_workspace_file.invoke(tool_args)
            else:
                res = "Tool not found."
            
            # Feed tool result back
            messages.append(response)
            messages.append(HumanMessage(content=f"Tool '{tool_name}' output:\n{res}"))
            
        # Final summary invocation
        response = llm_with_tools.invoke(messages)

    return {
        "messages": [response],
        "research_notes_path": "workspace/research_notes.md",
        "next_node": "writer"
    }


# ==========================================
# 2. PEDAGOGICAL WRITER NODE
# ==========================================
def writer_node(state: DeepAgentState) -> Dict[str, Any]:
    """
    Sub-Agent responsible for loading assigned Redaction Skill and drafting workspace/draft.md.
    """
    topic = state["topic"]
    skill_name = state.get("selected_redaction_skill", "redaction-feynman-deep-dive")
    print(f"\n✍️ [Writer Agent] Drafting article using skill: '{skill_name}'")

    # Load Skill content
    skill_content = skills_manager.get_skill_content(skill_name) or "Explain clearly."

    sys_prompt = WRITER_SYSTEM_PROMPT.format(
        topic=topic,
        redaction_skill_name=skill_name,
        redaction_skill_content=skill_content
    )

    llm = LLMFactory.get_model(provider=os.getenv("PROVIDER"), temperature=0.3)
    llm_with_tools = llm.bind_tools([read_workspace_file, write_workspace_file])

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content="Read workspace/research_notes.md and draft the complete article in workspace/draft.md.")
    ]

    response = llm_with_tools.invoke(messages)

    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            print(f"   🛠️ [Writer Tool Call] {tool_name}({tool_args})")
            
            if tool_name == "read_workspace_file":
                res = read_workspace_file.invoke(tool_args)
            elif tool_name == "write_workspace_file":
                res = write_workspace_file.invoke(tool_args)
            else:
                res = "Tool not found."
                
            messages.append(response)
            messages.append(HumanMessage(content=f"Tool output:\n{res}"))
            
        response = llm_with_tools.invoke(messages)

    return {
        "messages": [response],
        "draft_path": "workspace/draft.md",
        "next_node": "excalidraw"
    }


# ==========================================
# 3. EXCALIDRAW VISUAL ARCHITECT NODE
# ==========================================
def excalidraw_node(state: DeepAgentState) -> Dict[str, Any]:
    """
    Sub-Agent responsible for generating workspace/diagrams_spec.md using assigned Excalidraw Skill.
    """
    topic = state["topic"]
    skill_name = state.get("selected_excalidraw_skill", "excalidraw-pipeline-flow")
    print(f"\n🎨 [Excalidraw Agent] Designing diagrams using skill: '{skill_name}'")

    skill_content = skills_manager.get_skill_content(skill_name) or "Design simple diagrams."

    sys_prompt = EXCALIDRAW_SYSTEM_PROMPT.format(
        topic=topic,
        excalidraw_skill_name=skill_name,
        excalidraw_skill_content=skill_content
    )

    llm = LLMFactory.get_model(provider=os.getenv("PROVIDER"), temperature=0.2)
    llm_with_tools = llm.bind_tools([read_workspace_file, write_workspace_file])

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content="Read workspace/draft.md and write complete diagram specifications to workspace/diagrams_spec.md.")
    ]

    response = llm_with_tools.invoke(messages)

    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            print(f"   🛠️ [Excalidraw Tool Call] {tool_name}({tool_args})")
            
            if tool_name == "read_workspace_file":
                res = read_workspace_file.invoke(tool_args)
            elif tool_name == "write_workspace_file":
                res = write_workspace_file.invoke(tool_args)
            else:
                res = "Tool not found."
                
            messages.append(response)
            messages.append(HumanMessage(content=f"Tool output:\n{res}"))
            
        response = llm_with_tools.invoke(messages)

    return {
        "messages": [response],
        "diagrams_path": "workspace/diagrams_spec.md",
        "next_node": "supervisor"
    }


# ==========================================
# 🧪 TEST FOR SUB-AGENTS & STATE
# ==========================================
if __name__ == "__main__":
    print("🧪 Testing State Initialization & Agents...")
    
    test_state: DeepAgentState = {
        "messages": [],
        "topic": "LoRA & QLoRA Fine-Tuning Explained Visually",
        "selected_redaction_skill": "redaction-feynman-deep-dive",
        "selected_excalidraw_skill": "excalidraw-tensor-matrix",
        "skill_selection_rationale": "High mathematical complexity requires Feynman method and Tensor Matrix visualization.",
        "research_notes_path": None,
        "draft_path": None,
        "diagrams_path": None,
        "next_node": "researcher",
        "revision_feedback": None,
        "is_approved": False
    }

    print(f"✅ State initialized for topic: '{test_state['topic']}'")
    print(f"   Selected Redaction Skill: {test_state['selected_redaction_skill']}")
    print(f"   Selected Excalidraw Skill: {test_state['selected_excalidraw_skill']}")