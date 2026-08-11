from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class DeepAgentState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    topic: str
    selected_redaction_skill: Optional[str]
    selected_excalidraw_skill: Optional[str]
    skill_selection_rationale: Optional[str]
    research_notes_path: Optional[str]
    draft_path: Optional[str]
    diagrams_path: Optional[str]
    final_article_path: Optional[str] # <--- NOUVEAU
    next_node: Optional[str]
    revision_feedback: Optional[str]
    is_approved: bool