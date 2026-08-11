---
name: excalidraw-tensor-matrix
description: Use for tensor transformations, Query/Key/Value matrix multiplication, LoRA rank decomposition, and quantization grids.
version: 1.0.0
authors: ["Mohamed Nchourupouo"]
tags: ["excalidraw", "matrices", "tensors", "lora", "math"]
---

# Excalidraw Specification - Tensor & Matrix Operations

## Visual Directives
- **Layout:** 2D Grid block representations with explicitly annotated matrix dimensions (e.g., `[N x d]`).
- **LoRA Rank Decomposition Color Scheme:**
  - Base Weight Matrix W: Large Light Gray rectangle (`#f0f0f0`) `[d x k]`
  - Matrix A: Thin Vertical Pink rectangle (`#ffe6f0`) `[d x r]`
  - Matrix B: Thin Horizontal Blue rectangle (`#e6f2ff`) `[r x k]`
- **Annotations:** Draw hand-drawn curly braces indicating rank dimension `r` where `r << d`.