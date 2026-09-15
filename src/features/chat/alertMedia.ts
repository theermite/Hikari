// Relie une alerte Twitch (`chat-alert`) au média pop-up réglé pour elle (F-033/F-034,
// CDC §3quinquies) — la logique pure ici, le fil d'écoute dans `useAlertMedia`.
//
// [VEILLE] @tauri-apps/api@2.11.1 vérifié 2026-09-15 via registry.npmjs.org — même paquet
// déjà utilisé par `useChatAlerts.ts`, aucune dépendance neuve.

import { listen } from "@tauri-apps/api/event";
import { useEffect } from "react";
import { addTimedMedia } from "../scenes/api";
import type { ChatSettings } from "./chatSettings";
import type { AlertMediaRule, ChatAlert } from "./types";

/** Le nom donné à la source posée pour CETTE alerte — jamais le même nom deux alertes de
 * suite, sinon la seconde serait refusée tant que la première n'a pas expiré (le moteur
 * refuse un doublon dans une scène, `validate_source_name`). */
export function alertMediaSourceName(alertKind: string, atMs: number): string {
  return `${alertKind}-pop-up-${atMs}`;
}

/** Le réglage à appliquer pour `alert`, ou `null` si rien n'est configuré pour ce type —
 * pas de média par défaut : une alerte sans réglage ne doit rien afficher. */
export function ruleForAlert(
  alert: ChatAlert,
  mapping: ChatSettings["alertMedia"],
): AlertMediaRule | null {
  return mapping[alert.kind] ?? null;
}

/** Écoute les alertes Twitch et déclenche leur média réglé, s'il y en a un. */
export function useAlertMedia(settings: ChatSettings) {
  useEffect(() => {
    const unlisten = listen<ChatAlert>("chat-alert", (event) => {
      const rule = ruleForAlert(event.payload, settings.alertMedia);
      if (!rule) return;
      const name = alertMediaSourceName(event.payload.kind, Date.now());
      addTimedMedia(rule.scene, rule.kind, rule.path, name, rule.durationMs).catch(
        (error: unknown) => {
          console.error("alertMedia: addTimedMedia failed", error);
        },
      );
    });

    return () => {
      unlisten.then((f) => f());
    };
  }, [settings]);
}
