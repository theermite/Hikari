---
name: pre-rag-audit
description: Audit Knowledge Base before RAG indexation. Garbage in = garbage out.
model: opus
---

# /pre-rag-audit — Audit Knowledge Base Before RAG Indexation

> Audit a documentation corpus for coherence, duplicates, stale data, and exclusions BEFORE feeding it to a RAG pipeline. Garbage in = garbage out.

## Steps

1. **DETECT SCOPE**: Determine what to audit:
   - If run in a project repo: scan `docs/`, `README.md`, `CLAUDE.md`, `CHANGELOG.md`, and any `.md` files at root
   - If run with `--target skb`: scan SKB (Shinkofa Knowledge Base) via Obsidian MCP or filesystem (`D:/30-Dev-Projects/Eichi-Shinkofa/`) (806+ files, 18 domains)
   - If run with `--target <path>`: scan the specified directory

2. **RUN 7 CHECKS**:

   ### Check 1 — Version Coherence
   Scan all `.md` files for version patterns (`v4.0.X`, `version 4.0.X`, `Version: X.Y.Z`). Group by file. Alert if different files reference different versions of the same project.
   - **CRITICAL** if VERSION file disagrees with README/CLAUDE.md
   - **WARNING** if CHANGELOG last entry < current VERSION

   ### Check 2 — CHANGELOG Coherence
   - Detect multiple CHANGELOG files (EN/FR/other)
   - Alert if last CHANGELOG version != current VERSION
   - Alert if CHANGELOG stale (> 30 days without entry while commits exist)

   ### Check 3 — Metric Coherence
   Detect quantitative claims in docs: "X tests passing", "Y components", "Z files". Cross-reference with reality where possible (`pytest --collect-only`, `ls`, component count). Alert if drift > 5%.

   ### Check 4 — Exact Duplicates (hash)
   SHA-256 hash all `.md` files. Flag any files with identical content.

   ### Check 5 — Semantic Duplicates
   Detect when identical H1/H2 headings appear in multiple files (e.g., "## Security" documented in 3 places). Flag as potential divergence source.
   - **Quick mode**: heading comparison only
   - **Deep mode** (optional): embeddings + cosine similarity > 0.9

   ### Check 6 — Stale Data
   - "Last updated: YYYY-MM-DD" headers > 90 days old → WARNING
   - "Features vX.Y.Z" where X.Y.Z < current version → CRITICAL
   - References to files/classes that no longer exist → CRITICAL (requires `/update-registry` data if available)

   ### Check 7 — Exclusion Candidates
   Flag files that should NOT be indexed:
   - `_archive/*`, `archive/*`
   - `docs/Sessions/*` (historical context, not reference)
   - `docs/Research/*` (ephemeral veille data)
   - Files > 90 days without update containing status/feature claims
   - Duplicate language files (keep canonical, exclude other)

3. **GENERATE REPORT** as `docs/Pre-RAG-Audit-YYYY-MM-DD.md`:

   ```markdown
   # Pre-RAG Audit — <KB Name>

   **Date**: YYYY-MM-DD
   **Files scanned**: N markdown files
   **Mode**: quick / deep

   ## Executive Summary

   | Category | Critical | Warning | OK |
   |----------|----------|---------|-----|
   | Version coherence | 0 | 0 | N refs checked |
   | CHANGELOG coherence | 0 | 0 | - |
   | Metric coherence | 0 | 0 | - |
   | Exact duplicates | 0 | 0 | - |
   | Semantic duplicates | 0 | 0 | - |
   | Stale data | 0 | 0 | - |
   | Exclusion candidates | - | N | - |

   **Verdict**: READY FOR RAG / READY WITH WARNINGS / NOT READY

   ## Detailed Findings

   ### CRITICAL
   - C1: ...

   ### WARNINGS
   - W1: ...

   ## Indexation Recommendations

   ### Files to index (high priority)
   | File | Priority | Why |

   ### Files to EXCLUDE
   | File | Why |

   ## Recommended Pre-RAG Fixes
   1. [ ] <fix>
   ```

4. **GENERATE .ragignore** (if not exists): Propose a `.ragignore` file based on exclusion candidates. `.gitignore` syntax.

5. **DISPLAY VERDICT**: One of:
   - `READY FOR RAG` — 0 CRITICAL, 0 WARNING
   - `READY WITH WARNINGS` — 0 CRITICAL, N WARNINGS documented
   - `NOT READY` — CRITICAL findings must be resolved first

## Options

| Flag | Effect |
|------|--------|
| `--quick` | Skip semantic duplicate detection (Check 5 deep mode) |
| `--deep` | Enable embedding-based semantic duplicate detection |
| `--target <path>` | Scan a specific directory instead of current project |
| `--target skb` | Scan SKB (Shinkofa Knowledge Base) via filesystem (`D:/30-Dev-Projects/Eichi-Shinkofa/`) or Obsidian MCP |
| `--fix-auto` | Auto-fix trivial issues (update dates, remove exact dupes) |

## Rules

- **Pre-RAG audit is BLOCKING** — any (re)indexation of a knowledge base MUST be preceded by `/pre-rag-audit`. CRITICAL findings must be resolved. WARNINGS must be documented. Violation = RAG poisoning = `-10` session score.
- **QE V2 terminology coherence**: Verify Quality Pyramid levels, Human Quality Gates, Risk Classification levels are consistent across KB files and match `mnk/06-Quality.md` and `mnk/15-Human-Quality.md`.
- Run at minimum every 30 days on SKB
- Report is committed to git for traceability
- `.ragignore` is respected by SKB Knowledge Master agent during searches

## Connection to Other Chantiers

- **Chantier 002 (Registry)**: Cross-check doc references vs registry — if docs reference a class absent from registry, flag as stale
- **Skill `/session-start`**: Should remind if last pre-RAG audit on SKB > 30 days
- **SKB Knowledge Master agent**: Must respect `.ragignore` exclusions
