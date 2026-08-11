from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class DeepAgentState(TypedDict):
    """
    Shared memory state passed across nodes in the LangGraph execution flow.
    """
    # Message history with append reducer
    messages: Annotated[List[AnyMessage], add_messages]
    
    # User Request
    topic: str
    
    # Skills Selected by Skill Router
    selected_redaction_skill: Optional[str]
    selected_excalidraw_skill: Optional[str]
    skill_selection_rationale: Optional[str]
    
    # Generated Artifact Paths & States
    research_notes_path: Optional[str]
    draft_path: Optional[str]
    diagrams_path: Optional[str]
    
    # Human-in-the-Loop & Supervisor Control
    next_node: Optional[str]
    revision_feedback: Optional[str]
    is_approved: bool