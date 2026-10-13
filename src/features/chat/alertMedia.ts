// Relie une alerte Twitch (`chat-alert`) au média pop-up réglé pour elle (F-033/F-034,
// CDC §3quinquies) — la logique pure ici, le fil d'écoute dans `useAlertMedia`.
//
// [VEILLE] @tauri-apps/api@2.11.1 vérifié 2026-09-15 via registry.npmjs.org — même paquet
// déjà utilisé par `useChatAlerts.ts`, aucune dépendance neuve.

import { listen } from "@tauri-apps/api/event";
import { useEffect } from "react";
import { setSourceTransform, showMediaFor } from "../scenes/api";
import { OVERLAY_SCENE_NAME } from "../scenes/types";
import { requestScreen } from "../shell/panelActions";
import type { ChatSettings } from "./chatSettings";
import type { AlertMediaRule, ChatAlert } from "./types";

/** Le réglage à appliquer pour `alert`, ou `null` si rien n'est configuré pour ce type —
 * pas de média par défaut : une alerte sans réglage ne doit rien afficher. */
export function ruleForAlert(
  alert: ChatAlert,
  mapping: ChatSettings["alertMedia"],
): AlertMediaRule | null {
  return mapping[alert.kind] ?? null;
}

/** La taille de départ d'un média posé dans la médiathèque, en % de sa taille native. Une
 * image d'emote fait couramment 1592 px : à 100 % elle recouvre tout l'aperçu (Jay,
 * 2026-10-13). Ajustable ensuite à la souris sur l'aperçu. */
export const DEFAULT_MEDIA_SCALE_PERCENT = 20;

/** Où un média neuf se pose, en pixels du canevas — un peu à l'écart du coin, jamais collé
 * au bord. */
const DEFAULT_MEDIA_OFFSET_PX = 40;

/** Réduit et dégage un média qui vient d'être posé dans la médiathèque. À appeler UNE fois,
 * juste après l'ajout : un média déjà placé à la souris ne doit pas être remis à zéro. */
export function placeNewAlertMedia(kind: ChatAlert["kind"]): Promise<void> {
  return setSourceTransform(
    OVERLAY_SCENE_NAME,
    kind,
    DEFAULT_MEDIA_OFFSET_PX,
    DEFAULT_MEDIA_OFFSET_PX,
    DEFAULT_MEDIA_SCALE_PERCENT,
  );
}

/** Le temps laissé à l'aperçu natif pour réapparaître avant d'allumer le média de test. À
 * confirmer à l'écran (Jay) : une valeur trop courte reproduit le défaut, trop longue
 * ralentit le geste. */
export const TEST_SHOW_DELAY_MS = 700;

/** Le bouton « Tester » : ramène sur le cockpit, PUIS montre le média. Le chrono du média
 * court dès qu'il s'allume — le lancer avant que l'aperçu soit revenu l'éteignait pendant
 * le changement d'écran, sans que personne ne l'ait vu. */
export function previewAlertMedia(kind: ChatAlert["kind"], durationMs: number) {
  requestScreen("cockpit");
  setTimeout(() => {
    showMediaFor(OVERLAY_SCENE_NAME, kind, durationMs).catch(
      (error: unknown) => {
        console.error("alertMedia: test failed", error);
      },
    );
  }, TEST_SHOW_DELAY_MS);
}

/** Écoute les alertes Twitch et montre leur média réglé, s'il y en a un — la source vit
 * en PERMANENCE dans la médiathèque, sous le nom du type d'alerte : rien à recréer. */
export function useAlertMedia(settings: ChatSettings) {
  useEffect(() => {
    const unlisten = listen<ChatAlert>("chat-alert", (event) => {
      const rule = ruleForAlert(event.payload, settings.alertMedia);
      if (!rule) return;
      showMediaFor(
        OVERLAY_SCENE_NAME,
        event.payload.kind,
        rule.durationMs,
      ).catch((error: unknown) => {
        console.error("alertMedia: showMediaFor failed", error);
      });
    });

    return () => {
      unlisten.then((f) => f());
    };
  }, [settings]);
}
