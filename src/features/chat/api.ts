// Chat Tauri bridge — thin `invoke` wrapper, no logic here.

import { invoke } from "@tauri-apps/api/core";

/** Connecte le chat des comptes déjà utilisables (`chat_connect`, `chat/mod.rs`) — un
 * compte absent ou expiré ne tente aucune connexion, silencieusement. */
export function connectChat(): Promise<void> {
  return invoke("chat_connect");
}

/** Répond sur Twitch — la seule plateforme qui répond dans cette partie. */
export function sendChatMessage(text: string): Promise<void> {
  return invoke("chat_send", { text });
}

/** Coupe les connexions en cours — appelé à la fermeture du panneau Chat. */
export function disconnectChat(): Promise<void> {
  return invoke("chat_disconnect");
}
