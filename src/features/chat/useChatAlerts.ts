// Écoute les alertes Twitch (`chat-alert`) — la connexion elle-même est ouverte par
// `useChat` (même `chat_connect`/`chat_disconnect`, un seul cycle de vie pour tout le
// panneau) ; ce hook ne fait qu'accumuler ce qui arrive.

import { listen } from "@tauri-apps/api/event";
import { useEffect, useRef, useState } from "react";

import { pushAlert } from "./alerts";
import type { ChatAlert, DisplayedChatAlert } from "./types";

export function useChatAlerts() {
  const [alerts, setAlerts] = useState<DisplayedChatAlert[]>([]);
  const nextId = useRef(0);

  useEffect(() => {
    const unlisten = listen<ChatAlert>("chat-alert", (event) => {
      nextId.current += 1;
      setAlerts((history) => pushAlert(history, event.payload, nextId.current));
    });

    return () => {
      unlisten.then((f) => f());
    };
  }, []);

  return alerts;
}
