---
name: excalidraw-agent-state-machine
description: Use for agent graph architectures (LangGraph), feedback loops, router decision nodes, and Human-in-the-Loop interrupts.
version: 1.0.0
authors: ["Mohamed Nchourupouo"]
tags: ["excalidraw", "agent", "langgraph", "graph", "loop"]
---

# Excalidraw Specification - Agent State Machine & Graphs

## Visual Directives
- **Layout:** Circular or directed acyclic graph (DAG) structure with typed edges.
- **Node Shapes & Colors:**
  - Start / End Nodes: Oval / Pill shape.
  - Decision Router Node: Light Yellow Diamond (`#fffbe6`).
  - Action / Tool Nodes: Rounded Light Blue Rectangles (`#e6f2ff`).
  - Human-in-the-Loop (HITL) Interrupt: Light Red Octagon (`#ffe6e6`) with a pause/hand icon.
- **Feedback Loops:** Use curved recursive arrows clearly labeled with retry/validation conditions.