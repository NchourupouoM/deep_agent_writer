import os
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from src.config import LLMFactory
from src.skills_manager import SkillsManager
from src.state import DeepAgentState
from src.tools import (
    web_search_tavily,
    execute_python_sandbox,
    write_workspace_file,
    read_workspace_file
)
from src.prompts import (
    RESEARCHER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
    EXCALIDRAW_SYSTEM_PROMPT,
    EXCALIDRAW_MERGER_SYSTEM_PROMPT
)

skills_manager = SkillsManager(skills_dir="skills")


def extract_text_content(content: Any) -> str:
    """
    Extrait proprement le texte sous forme de chaîne de caractères (str) 
    qu'il s'agisse d'un str, d'une liste de dicts [{'type': 'text', 'text': '...'}] ou de TextBlocks.
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    parts.append(item["text"])
                elif "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(str(item))
            elif hasattr(item, "text"):
                parts.append(getattr(item, "text"))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    else:
        return str(content)


def execute_tool_call(tool_name: str, tool_args: dict) -> str:
    """Exécute l'outil approprié et retourne le résultat sous forme de chaîne."""
    if tool_name == "web_search_tavily":
        return web_search_tavily.invoke(tool_args)
    elif tool_name == "execute_python_sandbox":
        return execute_python_sandbox.invoke(tool_args)
    elif tool_name == "write_workspace_file":
        # S'assurer que content est un str propre
        if "content" in tool_args:
            tool_args["content"] = extract_text_content(tool_args["content"])
        return write_workspace_file.invoke(tool_args)
    elif tool_name == "read_workspace_file":
        return read_workspace_file.invoke(tool_args)
    return f"Error: Tool '{tool_name}' not found."


# ==========================================
# 1. RESEARCHER NODE
# ==========================================
def researcher_node(state: DeepAgentState) -> Dict[str, Any]:
    topic = state["topic"]
    print(f"\n🔍 [Researcher Agent] Starting deep research on: '{topic}'")

    llm = LLMFactory.get_model(provider=os.getenv("PROVIDER"), temperature=0.2)
    llm_with_tools = llm.bind_tools([web_search_tavily, execute_python_sandbox, write_workspace_file, read_workspace_file])

    sys_prompt = RESEARCHER_SYSTEM_PROMPT.format(topic=topic)
    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=f"Perform research and save findings to workspace/research_notes.md for: {topic}")
    ]

    response = llm_with_tools.invoke(messages)
    max_iters = 5
    iters = 0

    while response.tool_calls and iters < max_iters:
        iters += 1
        messages.append(response)

        for tool_call in response.tool_calls:
            t_name = tool_call["name"]
            t_args = tool_call["args"]
            print(f"   🛠️ [Researcher Tool] {t_name}({t_args})")
            t_res = execute_tool_call(t_name, t_args)
            messages.append(ToolMessage(content=str(t_res), tool_call_id=tool_call["id"]))

        response = llm_with_tools.invoke(messages)

    # Conversion garantie en str
    text_out = extract_text_content(response.content)

    if not os.path.exists("workspace/research_notes.md"):
        write_workspace_file.invoke({"filename": "research_notes.md", "content": text_out})

    print("   ✅ [Researcher Agent] Saved workspace/research_notes.md")
    return {
        "messages": [response],
        "research_notes_path": "workspace/research_notes.md",
        "next_node": "writer"
    }


# ==========================================
# 2. WRITER NODE
# ==========================================
def writer_node(state: DeepAgentState) -> Dict[str, Any]:
    topic = state["topic"]
    skill_name = state.get("selected_redaction_skill", "redaction-feynman-deep-dive")
    print(f"\n✍️ [Writer Agent] Drafting article using skill: '{skill_name}'")

    research_notes = read_workspace_file.invoke({"filename": "research_notes.md"})
    skill_content = skills_manager.get_skill_content(skill_name) or "Explain clearly."

    sys_prompt = WRITER_SYSTEM_PROMPT.format(
        topic=topic,
        redaction_skill_name=skill_name,
        redaction_skill_content=skill_content
    )

    llm = LLMFactory.get_model(provider=os.getenv("PROVIDER"), temperature=0.3)

    prompt = f"Research Notes:\n{research_notes}\n\nTask: Draft the complete article according to assigned skill guidelines. Include [EXCALIDRAW_DIAGRAM_X] placeholders."

    response = llm_with_tools = llm.invoke([
        SystemMessage(content=sys_prompt),
        HumanMessage(content=prompt)
    ])

    text_out = extract_text_content(response.content)
    write_workspace_file.invoke({"filename": "draft.md", "content": text_out})
    print("   ✅ [Writer Agent] Saved workspace/draft.md")

    return {
        "messages": [response],
        "draft_path": "workspace/draft.md",
        "next_node": "excalidraw"
    }


# ==========================================
# 3. EXCALIDRAW NODE
# ==========================================
def excalidraw_node(state: DeepAgentState) -> Dict[str, Any]:
    topic = state["topic"]
    skill_name = state.get("selected_excalidraw_skill", "excalidraw-pipeline-flow")
    print(f"\n🎨 [Excalidraw Agent] Designing diagrams using skill: '{skill_name}'")

    draft_content = read_workspace_file.invoke({"filename": "draft.md"})
    skill_content = skills_manager.get_skill_content(skill_name) or "Design simple diagrams."

    sys_prompt = EXCALIDRAW_SYSTEM_PROMPT.format(
        topic=topic,
        excalidraw_skill_name=skill_name,
        excalidraw_skill_content=skill_content
    )

    llm = LLMFactory.get_model(provider=os.getenv("PROVIDER"), temperature=0.2)

    prompt = f"Article Draft:\n{draft_content}\n\nTask: Generate complete diagram specifications for all [EXCALIDRAW_DIAGRAM_X] placeholders."

    response = llm.invoke([
        SystemMessage(content=sys_prompt),
        HumanMessage(content=prompt)
    ])

    text_out = extract_text_content(response.content)
    write_workspace_file.invoke({"filename": "diagrams_spec.md", "content": text_out})
    print("   ✅ [Excalidraw Agent] Saved workspace/diagrams_spec.md")

    return {
        "messages": [response],
        "diagrams_path": "workspace/diagrams_spec.md",
        "next_node": "excalidraw_merger"
    }


# ==========================================
# 4. EXCALIDRAW MERGER NODE
# ==========================================
def excalidraw_merger_node(state: DeepAgentState) -> Dict[str, Any]:
    topic = state["topic"]
    print(f"\n🧩 [Excalidraw Merger Agent] Merging draft and visual diagrams...")

    draft_content = read_workspace_file.invoke({"filename": "draft.md"})
    diagrams_content = read_workspace_file.invoke({"filename": "diagrams_spec.md"})

    sys_prompt = EXCALIDRAW_MERGER_SYSTEM_PROMPT.format(topic=topic)

    llm = LLMFactory.get_model(provider=os.getenv("PROVIDER"), temperature=0.2)

    prompt = f"Draft Article:\n{draft_content}\n\nDiagram Specs:\n{diagrams_content}\n\nTask: Replace all [EXCALIDRAW_DIAGRAM_X] placeholders in the draft with embedded ```excalidraw JSON blocks and generate the final complete article."

    response = llm.invoke([
        SystemMessage(content=sys_prompt),
        HumanMessage(content=prompt)
    ])

    # Extraction garantie en str pour éviter la Pydantic ValidationError
    final_text = extract_text_content(response.content)

    write_workspace_file.invoke({"filename": "final_article.md", "content": final_text})
    print("   ✅ [Merger Agent] Successfully saved workspace/final_article.md")

    return {
        "messages": [response],
        "final_article_path": "workspace/final_article.md",
        "next_node": "supervisor"
    }