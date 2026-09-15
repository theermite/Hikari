// Relie une alerte Twitch (`chat-alert`) au média pop-up réglé pour elle (F-033/F-034,
// CDC §3quinquies) — la logique pure ici, le fil d'écoute dans `useAlertMedia`.
//
// [VEILLE] @tauri-apps/api@2.11.1 vérifié 2026-09-15 via registry.npmjs.org — même paquet
// déjà utilisé par `useChatAlerts.ts`, aucune dépendance neuve.

import { listen } from "@tauri-apps/api/event";
import { useEffect } from "react";
import { showMediaFor } from "../scenes/api";
import { OVERLAY_SCENE_NAME } from "../scenes/types";
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

/** Écoute les alertes Twitch et montre leur média réglé, s'il y en a un — la source vit
 * en PERMANENCE dans la médiathèque, sous le nom du type d'alerte : rien à recréer. */
export function useAlertMedia(settings: ChatSettings) {
  useEffect(() => {
    const unlisten = listen<ChatAlert>("chat-alert", (event) => {
      const rule = ruleForAlert(event.payload, settings.alertMedia);
      if (!rule) return;
      showMediaFor(OVERLAY_SCENE_NAME, event.payload.kind, rule.durationMs).catch(
        (error: unknown) => {
          console.error("alertMedia: showMediaFor failed", error);
        },
      );
    });

    return () => {
      unlisten.then((f) => f());
    };
  }, [settings]);
}
