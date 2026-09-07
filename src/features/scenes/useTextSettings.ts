// La mémoire des réglages d'apparence des sources texte — extrait de ScenesPanel.tsx le
// 2026-09-08 (ce fichier dépassait déjà le plafond BLOQUANT de 500 lignes avant ce soir ;
// ajouter ici sans découper aurait aggravé une dette déjà présente).
//
// L'application est le SEUL auteur de ces réglages — rien d'autre ne les change — alors
// que les filtres d'une caméra sont aussi posés par le moteur, d'où leur aller-retour à
// eux. Deux sources de vérité là où il n'y a qu'un auteur créeraient une divergence sans
// raison.

import { emit, listen } from "@tauri-apps/api/event";
import {
  type RefObject,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { AudioSourceInfo } from "../audio/types";
import { saveSession } from "./sceneLayout";
import { toSession } from "./session";
import type { TextSettings } from "./textSettings";
import type { SceneInfo } from "./types";

/** Ce qu'une fenêtre de réglages séparée annonce quand elle change l'apparence d'un texte
 * (voir `SettingsWindow.tsx`). La fenêtre principale est la seule à retenir — d'où cet
 * écouteur, plutôt qu'une seconde copie de la logique de sauvegarde. */
interface TextSettingsChanged {
  scene: string;
  name: string;
  settings: TextSettings;
}

export function useTextSettings(
  stateRef: RefObject<SceneInfo[]>,
  activeRef: RefObject<string>,
  audioRef: RefObject<AudioSourceInfo[]>,
) {
  const [textSettings, setTextSettings] = useState<
    Record<string, Record<string, TextSettings>>
  >({});
  const textSettingsRef = useRef(textSettings);
  textSettingsRef.current = textSettings;

  /** Retient un réglage de texte, et le range dans la session.
   *
   * Écrit tout de suite plutôt qu'à la fermeture : une application fermée brutalement ne
   * sauvegarde rien, et c'est précisément le moment où l'on perd le plus. */
  const handleTextSettingsChange = useCallback(
    (scene: string, name: string, next: TextSettings) => {
      setTextSettings((avant) => {
        const apres = {
          ...avant,
          [scene]: { ...(avant[scene] ?? {}), [name]: next },
        };
        textSettingsRef.current = apres;
        return apres;
      });
      saveSession(
        toSession(
          stateRef.current,
          activeRef.current,
          audioRef.current,
          textSettingsRef.current,
        ),
      ).catch(() => undefined);
    },
    [stateRef, activeRef, audioRef],
  );

  // Une fenêtre de réglages SÉPARÉE (Jay, 2026-09-07 : « une fenêtre qui apparaît pour que
  // l'on puisse régler », comme dans OBS) applique elle-même ses changements au moteur,
  // mais ne les retient pas : la persistance de session reste à un seul endroit. Sans cet
  // écouteur, régler un texte depuis sa fenêtre s'appliquerait sans jamais survivre au
  // prochain lancement.
  useEffect(() => {
    const unlisten = listen<TextSettingsChanged>(
      "hikari://text-settings-changed",
      (event) => {
        handleTextSettingsChange(
          event.payload.scene,
          event.payload.name,
          event.payload.settings,
        );
      },
    );
    return () => {
      unlisten.then((f) => f());
    };
  }, [handleTextSettingsChange]);

  return {
    textSettings,
    textSettingsRef,
    handleTextSettingsChange,
    /** Écrit en mémoire SANS déclencher de sauvegarde — réservé au rejeu de session, qui
     * lit déjà la valeur depuis le disque : la réécrire ferait une sauvegarde inutile, et
     * la déclencher avant que le rejeu soit terminé romprait la garde qui protège la
     * session (voir `ScenesPanel.tsx`, « ce moteur est-il neuf ? »). */
    setTextSettingsFromReplay: setTextSettings,
  };
}

/** Réexporté pour que `SettingsWindow.tsx` émette l'événement avec le même nom, sans que
 * les deux fichiers puissent un jour diverger sur son orthographe. */
export const TEXT_SETTINGS_CHANGED_EVENT = "hikari://text-settings-changed";
export function emitTextSettingsChanged(
  payload: TextSettingsChanged,
): Promise<void> {
  return emit(TEXT_SETTINGS_CHANGED_EVENT, payload);
}
