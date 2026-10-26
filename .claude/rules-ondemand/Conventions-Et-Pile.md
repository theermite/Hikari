---
title: "Annexe — Conventions, nommage, git et pile technique"
created: 2026-10-26
updated: 2026-10-26
status: v2
type: annexe
project: Kata
---

# Annexe — Conventions, nommage, git et pile technique

> **Quand la lire** : avant d'écrire du code neuf, de nommer un fichier, de faire un commit ou de choisir une pile.
> **Pourquoi** : Ce sont des décisions internes : sans elles, chaque projet réinvente son nommage, son encodage et sa pile.
> Le texte ci-dessous est repris **tel quel** des anciennes règles (aucune retraduction : un marqueur
> traduit cesse de correspondre à son garde-fou). Les noms de règles qu'il cite sont les anciens ;
> la correspondance est dans `docs/regles/Couverture.md`.

<!-- source: Conventions.md#2 -->
**Language**: code (variables, functions, comments) = English ; docs / interactions /
content = French ; commit type/scope = English, description EN or FR ; i18n keys EN,
values FR (source) / EN / ES.

<!-- source: Conventions.md#4 -->
**Literal artefacts stay English, even inside a French doc** (Jay 2026-07-17): a French
doc has French prose, NOT translated identifiers. Keep in English: markers to emit
(`[VEILLE]`, `[ROBUSTNESS]`, `[SKB]`) · templates the AI emits verbatim (the
`TECHNICAL CHALLENGE` block) · enum values (`BLOCKING`, `robust`/`partial`/`modern`,
`Critical`/`Sensitive`/`Standard`) · approval words (`ok`, `go`, `lgtm`) · schema keys
(memory frontmatter) · anything inside backticks. Why: these are machine identifiers, not
prose — a translated marker stops matching its hook, and a template translated on one side
only creates two diverging formats. These short forms stay English (they drive behaviour);
Shinzo documents them in French. Proof: `scripts/check-translation-fidelity.py` fails if a
marker or identifier changes.

<!-- source: Conventions.md#5 -->
**Encoding**: UTF-8 without BOM, ALL files no exception. French accents preserved.
Hook-enforced. `.editorconfig` required (charset utf-8, lf). Git `core.autocrlf = input`.

<!-- source: Conventions.md#6 -->
**Docs = template + frontmatter (DEFAULT)**: every new markdown doc starts from its
template (in-repo `templates/` · vault docs `Shinzo/07-Methode/Templates/`) and carries
YAML frontmatter (title, created, updated, status, type). Why: homogeneous docs stay
navigable in Obsidian and consistent across the vault. Trigger: creating any new `.md`
doc (exempt: README, CHANGELOG, code files).

<!-- source: Conventions.md#7 -->
**Naming**:

| Context | Convention | Ex |
|---------|-----------|-----|
| Markdown docs | Title-Kebab-Case.md | Session-Report.md |
| Directories | Title-Kebab-Case/ | Platform-Blueprints/ |
| `.claude/agents`, `skills` | lowercase-kebab-case | code-quality-master.md |
| `.claude/rules` | NN-Title.md (numbered, load order) | 03-Qualite.md |  *[amendé 2026-10-26 : règles v2 numérotées]*
| Python | snake_case.py | auth_service.py |
| JS/TS utils | camelCase.ts | formatDate.ts |
| React | PascalCase.tsx | UserProfile.tsx |
| Bash | kebab-case.sh | run-backup.sh |
| CSS modules | kebab-case.module.css | user-card.module.css |

Exceptions: README, LICENSE, CHANGELOG, CLAUDE.md, SKILL.md, src/, docs/, tests/.

<!-- source: Conventions.md#8 -->
**Git**: branches `type/description-kebab-case` (feature/fix/hotfix/refactor/docs).
Conventional commits + `Co-Authored-By` mandatory. Types: feat, fix, refactor, docs,
chore, test, perf, ci, style.

<!-- source: Conventions.md#9 -->
**Atomic commits**: one logical change per commit. Hook-enforced.

<!-- source: Conventions.md#10 -->
**Stack — selection criterion (BLOCKING)**: stable, robust languages / platforms,
easy for the AI to maintain and debug. Priority = endurance over time (Monozukuri #6),
not fashion or raw performance.

<!-- source: Conventions.md#11 -->
**Stack defaults**:
- Backend: **Elixir/Phoenix** (default for all new backends, D24). FastAPI reserved for AI/ML pipelines.
- Desktop: **Tauri 2.x** by default ; Electron ONLY for heavy 3D.
- Frontend: Next.js 16+ / React 19 / TailwindCSS 4.
- DB: PostgreSQL 18. Cache: Redis 8. Job queue: Oban (Elixir).
- Package managers: pnpm (TS) / uv (Python) / mix (Elixir).
- Tri-Layer: TS (visible) + Elixir/Phoenix (backend) + Rust NIFs (critical modules) + Python (AI/ML).

<!-- source: Conventions.md#12 -->
**Schema source of truth**: Zod (front) / Ecto changesets (Elixir) / Pydantic
(Python). Never duplicate types — share via `@shinkofa/types`.

<!-- source: Conventions.md#13 -->
**Zero Dogma**: preferred stack, not mandatory. If a project needs something else,
justify and document.
