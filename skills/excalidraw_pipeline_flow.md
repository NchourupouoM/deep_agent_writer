---
name: excalidraw-pipeline-flow
description: Use for sequential execution flows, data pipelines, RAG generation pipelines, and step-by-step LLM inference.
version: 1.0.0
authors: ["Mohamed Nchourupouo"]
tags: ["excalidraw", "pipeline", "flow", "rag"]
---

# Excalidraw Specification - Sequential Pipeline Flow

## Visual Directives
- **Layout:** Horizontal flow (Left to Right: Input -> Processing -> Output).
- **Color Palette:**
  - User Input / Prompt: Light Blue Box (`#e6f2ff`, Blue stroke)
  - Data Processing / Embedding: Light Purple Box (`#f3e6ff`)
  - LLM / Core Engine: Light Orange Box (`#fff2e6`)
  - Output / Response: Light Green Box (`#e6ffe6`)
- **Elements:** Numbered step arrows (1️⃣, 2️⃣, 3️⃣) guiding the reader's eye sequentially.