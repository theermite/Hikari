// Préférences d'affichage du panneau Chat — persistées via tauri-plugin-store, même
// pattern que `settings/encodingSettings.ts`. Une seule pour l'instant : afficher l'heure
// devant chaque message (Jay, 2026-09-14 : « même si c'est en option »).

import { load, type Store } from "@tauri-apps/plugin-store";

const STORE_FILE = "chat-settings.json";
const SETTINGS_KEY = "settings";

export interface ChatSettings {
  showTimestamps: boolean;
}

export const DEFAULT_CHAT_SETTINGS: ChatSettings = {
  showTimestamps: false,
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
