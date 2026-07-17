---
name: extract-lego
description: Extract a component from the current project into @shinkofa/ui (Shinkofa-Shared). Full workflow from identification to verified replacement.
model: opus
---

# /extract-lego — Extract Component to Lego Library

Extract a component from the current project into `@shinkofa/ui` in Shinkofa-Shared. Run this from the SOURCE project (the one that has the component to extract).

## Prerequisites

- Shinkofa-Shared repo at `D:\30-Dev-Projects\Shinkofa-Shared`
- Current project imports or will import `@shinkofa/ui`

## Steps

1. **IDENTIFY**: Locate the component(s) to extract in the current project. Show Jay: file path, line count, dependencies, props interface. If the user described what they want in natural language, find it in the codebase.

2. **CHECK INVENTORY**: Search `@shinkofa/ui` for existing similar components. Check:
   - `Shinkofa-Shared/packages/ui/src/` for the component name
   - The Lego component list in `.claude/hooks/guards/write-guard.py`
   - If it already exists: STOP. Tell Jay and suggest importing instead.

3. **ANALYZE DEPENDENCIES**: List everything the component needs:
   - Internal imports (other components, utils, hooks)
   - External dependencies (npm packages)
   - Styles (CSS modules, Tailwind classes, inline)
   - Types (extract to `@shinkofa/types` if shared)
   - i18n keys (must use labels prop pattern, not hardcoded text)
   - Framework coupling (remove Next.js/framework specifics — library must be framework-agnostic)

4. **PLAN**: Present the extraction plan to Jay:
   - Target path in Shinkofa-Shared: `packages/ui/src/[category]/[ComponentName].tsx`
   - What changes vs the original (framework decoupling, labels prop, etc.)
   - Dependencies to add to Shinkofa-Shared
   - What the import will look like in the source project after extraction
   - Wait for validation before proceeding.

5. **CREATE IN SHINKOFA-SHARED**:
   - Write the component in `Shinkofa-Shared/packages/ui/src/[category]/`
   - Props interface: accept `labels` prop for all user-facing text (i18n pattern)
   - Remove framework coupling (no `next/link`, no `next/image` — use generic equivalents)
   - Respect: WCAG 2.2 AA, keyboard accessible, `prefers-reduced-motion`, themed (5 themes)
   - Max 300 lines per file. Split when a file exceeds 300 lines.

6. **TESTS**: Write tests in `Shinkofa-Shared/packages/ui/src/[category]/__tests__/`
   - Naming: `should_[action]_when_[condition]`
   - Cover: rendering, props, accessibility (axe), keyboard interaction, theme variants
   - Minimum 90% coverage for new components

7. **STORY**: Create Storybook story in `Shinkofa-Shared/packages/ui/src/[category]/[ComponentName].stories.tsx`
   - Default, with props variants, dark theme, mobile viewport

8. **EXPORT**: Add the component to the package public API:
   - Add export in `Shinkofa-Shared/packages/ui/src/index.ts`
   - Verify the component is importable: `import { ComponentName } from '@shinkofa/ui'`

9. **REPLACE IN SOURCE PROJECT**:
   - Delete the local component file
   - Replace all imports with `import { ComponentName } from '@shinkofa/ui'`
   - Connect i18n: add labels prop with `t('namespace:key')` values
   - Run source project tests to verify nothing broke

10. **UPDATE INVENTORY**:
    - Add component name to `write-guard.py` Lego list (in MNK-GoRin canonical + current project)
    - Update `[SHINZO]/02-Projets/Bibliotheque-Lego.md` (component count, category). Commit + push Shinzo.
    - Commit in both repos (Shinkofa-Shared + source project)

## Rules

- **Lego Library V2 Vision**: Components evolve toward functional modules (not just UI bricks) — complete features (e.g., a full calendar with all options, integrable by selecting which options to include). Absolutely modular. See `mnk/14-Eichi-Lego-Memory.md`.
- **Framework-agnostic**: No Next.js imports in @shinkofa/ui. Components receive callbacks and labels as props.
- **i18n via props**: Never hardcode text. The consumer project connects i18n to component props.
- **One component per extraction**: Don't batch. Extract, verify, commit, then next.
- **Verify in BOTH repos**: Shinkofa-Shared tests pass AND source project tests pass.
- **Atomic commits**: One commit in Shinkofa-Shared (new component), one in source project (replacement).

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
