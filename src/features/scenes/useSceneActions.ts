// Les gestes ordinaires sur une scène ou une source déjà posée — extrait de
// ScenesPanel.tsx le 2026-09-08 (ce fichier dépassait déjà le plafond BLOQUANT de 500
// lignes avant ce soir).
//
// Chacun de ces gestes n'ANTICIPE rien à l'écran : l'état affiché vient du moteur au
// message suivant. Un cadenas ou un œil qui changerait tout de suite mentirait si la
// commande échouait.

import {
  deleteScene,
  removeSource,
  reorderSource,
  setSourceLocked,
  setSourceVisible,
  switchScene,
} from "./api";
import type { SceneLayout } from "./sceneLayout";
import type { SourceOrder } from "./types";

export function useSceneActions(
  setActionError: (message: string | null) => void,
  layout: SceneLayout,
  persist: (next: SceneLayout) => void,
  setConfirmingDelete: (name: string | null) => void,
) {
  const activate = (name: string, transitionMs: number) => {
    setActionError(null);
    switchScene(name, transitionMs).catch((error: unknown) =>
      setActionError(String(error)),
    );
  };

  const confirmDelete = (name: string) => {
    setActionError(null);
    setConfirmingDelete(null);
    deleteScene(name)
      .then(() => {
        // L'étiquette et la position d'une scène disparue n'ont plus de sens : les garder
        // ferait réapparaître un ancien nom si une future scène reprenait cet identifiant.
        const { [name]: _removed, ...labels } = layout.labels;
        persist({ order: layout.order.filter((n) => n !== name), labels });
      })
      .catch((error: unknown) => setActionError(String(error)));
  };

  // Nommé sans ambiguïté : un `reorder` de scène plus haut déplace une SCÈNE dans la
  // liste, celui-ci déplace une SOURCE dans la pile d'une scène.
  const reorderInScene = (
    scene: string,
    name: string,
    direction: SourceOrder,
  ) => {
    setActionError(null);
    reorderSource(scene, name, direction).catch((error: unknown) =>
      setActionError(String(error)),
    );
  };

  const removeFromScene = (scene: string, name: string) => {
    setActionError(null);
    removeSource(scene, name).catch((error: unknown) =>
      setActionError(String(error)),
    );
  };

  const toggleLock = (scene: string, name: string, locked: boolean) => {
    setActionError(null);
    setSourceLocked(scene, name, locked).catch((error: unknown) =>
      setActionError(String(error)),
    );
  };

  const toggleVisible = (scene: string, name: string, visible: boolean) => {
    setActionError(null);
    setSourceVisible(scene, name, visible).catch((error: unknown) =>
      setActionError(String(error)),
    );
  };

  return {
    activate,
    confirmDelete,
    reorderInScene,
    removeFromScene,
    toggleLock,
    toggleVisible,
  };
}
