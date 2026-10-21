---
name: scopture-cli
description: "Inspect, query, mutate, diff, render, and export Scopture/DUC (`.duc`) drawings from the terminal with the `scopture` CLI. Use whenever the user has a local `.duc` file or remote drawing and wants to see what's in it, find or filter elements, run read-only or mutative SQL, mutate drawing state or elements via the Python sandbox, compare two versions, render a preview image, extract embedded STEP/IFC files, export to STEP/DXF, review a drawing's charter or issues, or open it in the desktop app, even if they never mention the CLI. For understanding Scopture canvas standards specifically use the `scopture` skill; for writing `ducpy` code or adjacent logic to the `.duc` use the `duc` skill."
---

# Scopture CLI

The `scopture` CLI ships with the Scopture desktop app. It works on local `.duc` files (gzip-compressed SQLite) and on remote drawings. It is built for shell pipelines: it inspects, queries, mutates, diffs, renders, and exports.

## Before you start

1. Run `scopture --version`. If it isn't found, tell the user to install the Scopture app via `https://site.scopture.com/download`, and offer the `duc` skill as a way to read the file without the CLI.
2. Run `scopture <command> --help` before using any flag not shown below. Flags change; `--help` is authoritative.
3. Pick an output mode: `--raw` for piping into `jq`/`grep`/`head`, `--json` when you need an explicit `{"success": true, "data": ...}` envelope.

## Side effects

- **Read-only:** `ls`, `cat`, `elements`, `run-sql` (default read-only), `diff`, `files list`, `charter get`, `issues list`, `drawing get`, `auth status`, `ps`, `desktop status`.
- **Mutates drawing state:**
  - `run-python`: executes Python scripts in the sandbox. If `update_drawing(patch)` is called, modifies drawing elements and atomically re-compresses local `.duc` files or commits remote drawing changes.
  - `run-sql --mutate`: executes mutative SQL statements directly, persisting changes to local `.duc` files or remote drawings.
- **Writes a file:** `render`, `export`, `files extract`. Direct output with `-o` to a scratch or outputs directory, never over the user's source drawing.
- **Changes the user's screen:** `scopture <file>`, `open`, `desktop focus`. Run these only when the user asks to open or show something. For inspection and background scripts, use the headless commands.

## Inspect

Drawings can hold thousands of elements. Never print a full `cat` into the conversation; start with `ls` for the shape of the drawing, then narrow.

```bash
scopture ls model.duc                          # tabular overview
scopture cat model.duc | grep -i motor | head  # NDJSON stream, one element per line
scopture elements list model.duc --type model --search "bracket"
scopture elements get model.duc <element-id>   # full geometry and parametric code
```

## Query & Mutate SQL (`run-sql`)

Discover the schema before writing queries rather than guessing column names:

```bash
# Read-only query (default)
scopture run-sql model.duc "SELECT name FROM sqlite_master WHERE type='table'"
scopture run-sql model.duc "SELECT id, element_type, label FROM elements LIMIT 10"
cat query.sql | scopture run-sql model.duc - --raw | jq .   # query from stdin

# Mutative SQL (--mutate flag)
scopture run-sql model.duc "UPDATE elements SET label = 'Front Bracket' WHERE id = 'elem-1'" --mutate
scopture run-sql model.duc "INSERT INTO layers (id, name, is_visible) VALUES ('layer-mfg', 'Manufacturing', 1)" --mutate
```

> [!NOTE]
> On local `.duc` files, `--mutate` executes in read-write mode, flushes WAL, and atomically re-compresses the `.duc` file.
> On remote drawings, `--mutate` commits the SQL transaction to the drawing. For remote read-only queries with multiple databases, see `duc` skill for the `{db}` placeholder.

## Drawing State & Element Mutation via Python (`run-python`)

To create or update drawing state (elements, 2D geometry, parametric 3D models, layers, blocks, or global state), use `scopture run-python`.

This command runs scripts in Scopture's **drawing-level Python runtime environment** (the same runtime accessible via the Scopture MCP server), executing against the drawing as a whole rather than being bound to any single element:

```bash
# Execute inline Python script against the drawing
scopture run-python model.duc "update_drawing({'elements': [{'id': 'box-1', 'element_type': 'rectangle', 'x': 100, 'y': 150, 'width': 200, 'height': 80}]})"

# Run a Python script from a file
scopture run-python model.duc --file ./create_parametric_bracket.py

# Pipe Python script via STDIN
cat mutate.py | scopture run-python model.duc -
```

> [!TIP]
> **Cross-Skill References**
> - **Canvas Patch & Styling Rules**: For patch semantics (`ADD`/`UPDATE`/`DELETE`), injected sandbox helpers, scientific libraries, and visual design standards, consult the **`scopture`** skill (and its bundled `./docs/` folder).
> - **Programmatic Modeling & `.duc` Architecture**: For `ducpy` fluent builders, relational tables, and SQLite schema guidance, consult the **`duc`** skill (and its bundled `./docs/` and `./docs-ducpy` folders).

## Diff, render, export

```bash
scopture diff baseline.duc modified.duc       # + added, - removed, ~ modified
scopture render model.duc -o preview.png
scopture render model.duc -o element.png --element <element-id> --width 1920 --height 1080
scopture export model.duc --format step -o ./part.step   # also: --format dxf
scopture files list model.duc
scopture files extract model.duc <file-id> -o ./extracted_part.step
```

After rendering, open the image and look at it before describing the result to the user.

## Remote drawings

The target can be a local path or a remote drawing UUID/slug. The CLI reuses the desktop app's login (OS credential store), so there is no separate sign-in.

```bash
scopture ls                          # no target: lists accessible remote drawings
scopture drawing get <drawing-id>
scopture auth status
```

## Review

```bash
scopture charter get model.duc       # requirements (MUST/SHOULD), constraints, decisions
scopture issues list model.duc       # open/closed issues and reviewer threads
```

## Common workflows

- **Find an element and show it:** `cat | grep` to locate it, take its ID, `elements get` to inspect it, `render --element` to see it, then view the PNG.
- **Mutate elements or add parametric models:** Write a small Python script using `update_drawing(...)`, run `scopture run-python model.duc --file script.py`, then `render` to verify.
- **What changed between two versions:** `diff`, then summarize the added/removed/modified counts and call out the notable elements. Render both if the change is visual.
- **Review briefing:** `charter get` + `issues list` + `diff` against the previous version.

## Exit codes

| Code | Meaning | What to do |
|---|---|---|
| 0 | Success | |
| 2 | Authentication failure | Run `scopture auth status`; ask the user to sign in through the desktop app |
| 3 | Target, element, or file not found | Run `scopture ls` to confirm the target and IDs |
| 4 | Invalid arguments or query syntax | Check `--help`; for SQL, re-check table and column names |
| 5 | Render error | Retry with a specific `--element` or a smaller size |
