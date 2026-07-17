---
name: update-registry
description: Regenerate Code Registry — auto-scan project source and generate structured inventory.
model: sonnet
---

# /update-registry — Regenerate Code Registry

> Auto-scan project source code via AST and generate a structured inventory of classes, methods, and functions.

## Steps

1. **DETECT PROJECT TYPE**: Check for `pyproject.toml` / `setup.py` (Python), `package.json` / `tsconfig.json` (TypeScript), or both (hybrid). Display detected type.

2. **SCAN SOURCE CODE**:
   - **Python**: Use `ast` module (stdlib) to scan `src/` (or project root if no `src/`). Extract classes (with methods, bases, docstrings), top-level functions (with signatures, docstrings), and async variants.
   - **TypeScript**: Use `ts-morph` to scan `src/` or `packages/*/src/`. Extract classes, interfaces, type aliases, exported functions, React components.
   - **Exclusions**: Respect `.registryignore` if present. Default exclusions: `tests/`, `node_modules/`, `venv/`, `__pycache__/`, `dist/`, `build/`, `.next/`, `.astro/`, `migrations/`, `*.gen.ts`, `*_pb2.py`.

3. **GENERATE OUTPUT** in `docs/registry/`:
   - `INDEX.md` — Summary table with counts per category + links to detail files
   - One `.md` per category (grouped by directory: `core.md`, `ui.md`, `utils.md`, etc.)
   - `signatures.jsonl` — Machine-readable format (1 line per symbol: kind, name, file, line, methods/signature, docstring)

4. **DIFF REPORT**: Compare with previous registry (if exists) via `git diff docs/registry/`. Display:
   - New symbols added
   - Symbols removed (potential dead code or breaking change)
   - Symbols modified (signature change)

5. **DISPLAY SUMMARY**:
   ```
   Registry updated: X classes, Y methods, Z functions
   New: +N | Removed: -N | Modified: ~N
   ```

## Output Format

### INDEX.md
```markdown
# Registry — <Project Name>

**Generated**: YYYY-MM-DD HH:MM
**Source**: AST scan of `src/`
**Scanner**: Python ast / ts-morph

| Category | Classes | Methods | Functions | File |
|----------|---------|---------|-----------|------|
| core     | 25      | 165     | 19        | [core.md](core.md) |
| ...      | ...     | ...     | ...       | ...  |
| **Total**| **X**   | **Y**   | **Z**     |      |

## Usage

Before creating a new function/class:
1. Search this registry for the functionality you need
2. If found, import and reuse
3. If not found, create it and run `/update-registry`
```

### Category file (e.g., core.md)
```markdown
# Registry — core/

## Classes

### ClassName
- **File**: `src/core/module.py:42`
- **Inherits**: BaseClass
- **Methods**: method_a, method_b, method_c
- **Docstring**: "Brief description..."

## Functions

### function_name
- **File**: `src/core/utils.py:15`
- **Signature**: `(config: Config) -> Result`
- **Docstring**: "Brief description..."
```

### signatures.jsonl
```jsonl
{"kind":"class","name":"AudioCapture","file":"src/core/audio_capture.py","line":42,"methods":["start","stop"],"inherits":[],"docstring":"..."}
{"kind":"function","name":"create_processor","file":"src/core/processor.py","line":15,"signature":"(config: Config) -> Processor","docstring":"..."}
```

## .registryignore

Optional file at project root (`.gitignore` syntax) to exclude paths from scanning:
```
tests/
node_modules/
venv/
dist/
migrations/
*.gen.ts
```

## Rules

- Registry is **descriptive**, not prescriptive — it documents what exists, not what should exist
- Run after adding/removing/renaming classes or functions
- CI can verify registry is up-to-date: `git diff --exit-code docs/registry/`
- For `@shinkofa/*` packages: registry replaces the manual inventory in `rules/Quality.md` over time
- Generated files are committed to git (human-readable documentation)
- `signatures.jsonl` can be used by other tools (search, duplicate detection, `/pre-rag-audit`)

## Connection to Lego Library

When run on `Shinkofa-Shared/packages/ui/`, the registry serves as the **auto-generated component inventory** — replacing the manually maintained table in `rules/Quality.md`. The rule "check inventory before coding" then points to the registry instead of a static table.
