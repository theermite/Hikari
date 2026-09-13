// Connecte le chat à l'ouverture du panneau, le coupe à sa fermeture — même principe que
// `engine_lifecycle` pour l'Aperçu (une ressource réseau ne tourne que pendant qu'un
// panneau en a besoin), jamais 100 % du temps où l'app est ouverte.

import { listen } from "@tauri-apps/api/event";
import { useCallback, useEffect, useRef, useState } from "react";

import { connectChat, disconnectChat, sendChatMessage } from "./api";
import { pushChatMessage } from "./history";
import type { ChatMessage, DisplayedChatMessage } from "./types";

export function useChat() {
  const [messages, setMessages] = useState<DisplayedChatMessage[]>([]);
  const nextId = useRef(0);

  useEffect(() => {
    const unlisten = listen<ChatMessage>("chat-message", (event) => {
      nextId.current += 1;
      setMessages((history) =>
        pushChatMessage(history, event.payload, nextId.current),
      );
    });

    connectChat().catch((error: unknown) => {
      console.error("chat: chat_connect failed", error);
    });

    return () => {
      unlisten.then((f) => f());
      disconnectChat().catch((error: unknown) => {
        console.error("chat: chat_disconnect failed", error);
      });
    };
  }, []);

  const send = useCallback((text: string) => {
    return sendChatMessage(text).catch((error: unknown) => {
      console.error("chat: chat_send failed", error);
    });
  }, []);

  return { messages, send };
}
