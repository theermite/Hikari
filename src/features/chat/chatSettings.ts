// Préférences d'affichage du panneau Chat — persistées via tauri-plugin-store, même
// pattern que `settings/encodingSettings.ts`. Une seule pour l'instant : afficher l'heure
// devant chaque message (Jay, 2026-09-14 : « même si c'est en option »).

import { load, type Store } from "@tauri-apps/plugin-store";
import type { AlertMediaRule, ChatAlert } from "./types";

const STORE_FILE = "chat-settings.json";
const SETTINGS_KEY = "settings";

export interface ChatSettings {
  showTimestamps: boolean;
  /** Un média pop-up (F-033/F-034) par type d'alerte — absent = aucun déclenchement. */
  alertMedia: Partial<Record<ChatAlert["kind"], AlertMediaRule>>;
}

export const DEFAULT_CHAT_SETTINGS: ChatSettings = {
  showTimestamps: false,
  alertMedia: {},
};

let storePromise: Promise<Store> | null = null;

function getStore(): Promise<Store> {
  storePromise ??= load(STORE_FILE, { autoSave: true });
  return storePromise;
}

export async function loadChatSettings(): Promise<ChatSettings> {
  const store = await getStore();
  const saved = await store.get<ChatSettings>(SETTINGS_KEY);
  return saved ?? DEFAULT_CHAT_SETTINGS;
}

export async function saveChatSettings(settings: ChatSettings): Promise<void> {
  const store = await getStore();
  await store.set(SETTINGS_KEY, settings);
}

/** Pose SEULEMENT les champs donnés, en relisant le store juste avant d'écrire — jamais
 * depuis un état local chargé une fois au montage. Le panneau Chat (bouton horloge) et
 * l'écran de réglage des alertes écrivent le MÊME fichier ; réécrire l'objet entier
 * depuis un état périmé effacerait silencieusement ce que l'autre vient de poser (même
 * défaut déjà vécu sur l'encodage, `encodingSettings.ts`, 2026-09-13). */
export async function patchChatSettings(
  over: Partial<ChatSettings>,
): Promise<ChatSettings> {
  const current = await loadChatSettings();
  const next = { ...current, ...over };
  await saveChatSettings(next);
  return next;
}
