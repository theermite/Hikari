// Renommer une scène — extrait de ScenesPanel.tsx le 2026-09-08 (ce fichier dépassait déjà
// le plafond BLOQUANT de 500 lignes avant ce soir).
//
// La scène n'est JAMAIS renommée côté moteur — son identifiant y reste fixe à vie. Ce qui
// change ici est l'étiquette LISIBLE, portée par l'application (voir `sceneLayout.ts`).

import { useEffect, useRef, useState } from "react";
import { labelFor, type SceneLayout, validateLabel } from "./sceneLayout";

const LABEL_ERRORS = {
  empty: "Le nom ne peut pas être vide.",
  duplicate: "Une autre scène porte déjà ce nom.",
} as const;

export function useSceneRename(
  layout: SceneLayout,
  persist: (next: SceneLayout) => void,
) {
  const [renaming, setRenaming] = useState<string | null>(null);
  const [draftLabel, setDraftLabel] = useState("");
  const [labelError, setLabelError] = useState<string | null>(null);
  const renameInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (renaming) renameInput.current?.focus();
  }, [renaming]);

  const startRename = (name: string) => {
    setLabelError(null);
    setRenaming(name);
    setDraftLabel(labelFor(name, layout));
  };

  const submitRename = (name: string, sceneNames: string[]) => {
    const verdict = validateLabel(draftLabel, name, sceneNames, layout);
    if (verdict !== "ok") {
      setLabelError(LABEL_ERRORS[verdict]);
      return;
    }
    persist({
      ...layout,
      labels: { ...layout.labels, [name]: draftLabel.trim() },
    });
    setRenaming(null);
  };

  return {
    renaming,
    draftLabel,
    setDraftLabel,
    labelError,
    renameInput,
    startRename,
    submitRename,
    cancelRename: () => setRenaming(null),
  };
}
