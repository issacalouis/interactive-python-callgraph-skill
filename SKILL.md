---
name: interactive-python-callgraph
description: Generate an interactive HTML function call graph from Python files or Jupyter notebooks. Use when a user wants to review real function source through connected nodes, inspect code relationships visually, hover or click nodes to open exact code, or requests a function relationship/call graph rather than prose documentation.
---

# Interactive Python Call Graph

Create a review-oriented HTML graph whose nodes are Python functions and whose directed edges represent real function calls.

## Workflow

1. Identify the `.py` or `.ipynb` source and the requested scope. If the user names a section such as “问题一”, include its functions plus the functions they actually call. Exclude constants, datasets, imports, classes, and explanatory pseudo-nodes unless explicitly requested.
2. Run `scripts/build_callgraph.py`. Prefer `--roots` when the user identifies one or more entry functions; this keeps only the entry functions and their transitive dependencies.
3. Preserve source faithfully. The expanded node must show the exact function text extracted from the current source, not a summary or rewritten version.
4. Verify the generated graph:
   - every displayed node maps to a real function definition;
   - every edge maps to a call found in the parsed syntax tree;
   - no data or constant nodes appear by default;
   - the embedded source for each node exactly matches the source file;
   - the HTML parses and its inline JavaScript has valid syntax.
5. Deliver the HTML. Explain that the graph library loads from a pinned CDN URL and therefore needs network access when opened.

## Interaction contract

- Keep each function as a compact block.
- Draw arrows from callee to caller so dependencies flow toward entry points.
- Keep a permanently visible responsive source inspector beside the graph from initial load, including an empty state. Selecting or clearing a function must not change the graph's width or position.
- Open source only on explicit node clicks. Hover must never open, close, or resize an inspector. Canvas clicks and dragging keep the inspector open; close explicitly or with Escape.
- Use a restrained scientific palette with muted blue/teal/ochre/purple depth colors and readable light-background source. Soft gradients, a subtle dot grid, and light shadows may add depth; keep decoration low contrast and subordinate to functions and code.
- Show clickable caller and callee function links in the inspector without adding relationship nodes to the graph.
- Provide search, fit-to-screen, layout-direction, close, and copy-source controls.
- Use color only to distinguish dependency depth or broad calculation stages; never replace actual code with descriptions.
- Set node fill, border, hover, and selected colors explicitly from the same muted palette so library defaults cannot introduce saturated colors during interaction.

## Command

```text
python scripts/build_callgraph.py SOURCE --output OUTPUT.html [--roots function_a function_b]
```

The script uses only the Python standard library. It reads notebooks as JSON and Python files as text.
