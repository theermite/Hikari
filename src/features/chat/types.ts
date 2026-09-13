// Mirrors `ChatMessage` (chat/mod.rs) — un message reçu de Twitch ou YouTube, tel que le
// backend l'émet sur l'événement `chat-message`.

export type ChatPlatform = "twitch" | "youtube";

export interface ChatMessage {
  platform: ChatPlatform;
  username: string;
  text: string;
}

// Un message tel que le panneau l'affiche — porte un identifiant stable pour la clé de
// liste React, que le backend ne fournit pas (un message de chat n'a pas d'identité
// propre côté plateforme).
export interface DisplayedChatMessage extends ChatMessage {
  id: number;
}
