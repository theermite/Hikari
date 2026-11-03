---
name: extract-lego
description: Extract a component from the current project into @shinkofa/ui (Toolbox/typescript). Full workflow from identification to verified replacement.
model: sonnet
---

# /extract-lego — Extract Component to Lego Library

> **Annexes à lire** (`.claude/rules-ondemand/`, un garde-fou bloque l'écriture sinon) : `Interface` (bibliothèque de pièces, inventaire généré, module morphique).

Extract a component from the current project into `@shinkofa/ui` in Toolbox (`typescript/`). Run this from the SOURCE project (the one that has the component to extract).

> Shinkofa-Shared a fusionné dans Toolbox le 2026-11-02 : son dossier d'origine est **gelé**, la source unique est `Toolbox/typescript/`. Ne rien écrire dans l'ancien dossier.

## Prerequisites

- Toolbox repo at `D:\30-Dev-Projects\Toolbox` (packages in `typescript/packages/`). Règle n°1 de Toolbox : un commit qui ajoute, retire, renomme ou change l'état ou la version d'une brique met à jour `index/briques.yaml` dans le même commit (puis `python scripts/generate-index.py` ; `python scripts/check-index.py` avant de commiter).
- Current project imports or will import `@shinkofa/ui`

## Steps

1. **IDENTIFY**: Locate the component(s) to extract in the current project. Show Jay: file path, line count, dependencies, props interface. If the user described what they want in natural language, find it in the codebase.

2. **CHECK INVENTORY**: Search `@shinkofa/ui` for existing similar components. Check:
   - `Toolbox/typescript/packages/ui/src/` for the component name
   - The generated inventory (`.claude/hooks/lib/ui_inventory.py` reads the live package; snapshot `lego/ui-inventory.json`) and `Toolbox/INDEX.md`
   - If it already exists: STOP. Tell Jay and suggest importing instead.

3. **ANALYZE DEPENDENCIES**: List everything the component needs:
   - Internal imports (other components, utils, hooks)
   - External dependencies (npm packages)
   - Styles (CSS modules, Tailwind classes, inline)
   - Types (extract to `@shinkofa/types` if shared)
   - i18n keys (must use labels prop pattern, not hardcoded text)
   - Framework coupling (remove Next.js/framework specifics — library must be framework-agnostic)

4. **PLAN**: Present the extraction plan to Jay:
   - Target path in Toolbox: `typescript/packages/ui/src/[category]/[ComponentName].tsx`
   - What changes vs the original (framework decoupling, labels prop, etc.)
   - Dependencies to add to `typescript/packages/ui/package.json`
   - What the import will look like in the source project after extraction
   - Announce in one sentence what will be extracted, then do it. No approval round (doctrine § 2).

5. **CREATE IN TOOLBOX**:
   - Write the component in `Toolbox/typescript/packages/ui/src/[category]/`
   - Props interface: accept `labels` prop for all user-facing text (i18n pattern)
   - Remove framework coupling (no `next/link`, no `next/image` — use generic equivalents)
   - Respect: WCAG 2.2 AA, keyboard accessible, `prefers-reduced-motion`, themed (5 themes)
   - Max 300 lines per file. Split when a file exceeds 300 lines.

6. **TESTS**: Write tests in `Toolbox/typescript/packages/ui/src/[category]/__tests__/`
   - Naming: `should_[action]_when_[condition]`
   - Cover: rendering, props, accessibility (axe), keyboard interaction, theme variants
   - Minimum 90% coverage for new components

7. **STORY**: Create Storybook story in `Toolbox/typescript/packages/ui/src/[category]/[ComponentName].stories.tsx`
   - Default, with props variants, dark theme, mobile viewport

8. **EXPORT**: Add the component to the package public API:
   - Add export in `Toolbox/typescript/packages/ui/src/index.ts`
   - Verify the component is importable: `import { ComponentName } from '@shinkofa/ui'`

9. **REPLACE IN SOURCE PROJECT**:
   - Delete the local component file
   - Replace all imports with `import { ComponentName } from '@shinkofa/ui'`
   - Connect i18n: add labels prop with `t('namespace:key')` values
   - Run source project tests to verify nothing broke

10. **UPDATE INVENTORY**:
    - L'inventaire se lit dans le code : plus de liste de composants à tenir à la main dans `write-guard.py`. Régénérer l'instantané propagé avec `python scripts/generate-ui-inventory.py` (dans Kata), puis le propager avec la méthode.
    - Update `Toolbox/index/briques.yaml` if the brick's state or version changed (same commit, rule n°1), and `[SHINZO]/02-Projets/Bibliotheque-Lego.md` (component count, category). Commit + push Shinzo.
    - Commit in both repos (Toolbox + source project)

## Rules

- **Lego Library V2 Vision**: Components evolve toward functional modules (not just UI bricks) — complete features (e.g., a full calendar with all options, integrable by selecting which options to include). Absolutely modular. See `.claude/rules/05-Savoir.md`.
- **Framework-agnostic**: No Next.js imports in @shinkofa/ui. Components receive callbacks and labels as props.
- **i18n via props**: Never hardcode text. The consumer project connects i18n to component props.
- **One component per extraction**: Don't batch. Extract, verify, commit, then next.
- **Verify in BOTH repos**: Toolbox tests pass (`pnpm test` in `typescript/`) AND source project tests pass.
- **Atomic commits**: One commit in Toolbox (new component), one in source project (replacement).

## Example

```
User: "Extrais le formulaire de contact de The Ermite"

Takumi:
1. Found: src/components/ContactForm.tsx (87 lines)
2. Not in @shinkofa/ui inventory — proceed
3. Dependencies: React, Zod schema, Textarea, Button (already in @shinkofa/ui), fetch API
4. Plan: packages/ui/src/forms/ContactForm.tsx, labels prop for 6 strings, onSubmit callback
5-8. Create, test, story, export
9. Replace in The Ermite: import { ContactForm } from '@shinkofa/ui' + labels via t()
10. Update inventory: +1 component (70 total)
```
