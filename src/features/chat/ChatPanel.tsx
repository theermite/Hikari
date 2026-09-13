// Panneau Chat — première partie de la brique Interaction : lecture fusionnée Twitch +
// YouTube, filtre par plateforme, réponse sur Twitch. Modération, alertes, bandeaux et
// objectifs restent hors de cette partie (voir le découpage convenu avec Jay, 2026-09-14) —
// le panneau ne les promet plus tant qu'ils ne sont pas construits (Dignity : jamais un
// bouton qui prétend faire quelque chose qu'il ne fait pas).

import { invoke } from "@tauri-apps/api/core";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useState } from "react";

import { Panel } from "../../components/ui/Panel";
import { filterChatMessages } from "./history";
import type { ChatPlatform } from "./types";
import { useChat } from "./useChat";

type Connection = "absent" | "live" | "a_renouveler";

interface StoredStatus {
  twitch: Connection;
  youtube: Connection;
}

/** Un des deux comptes est-il réellement utilisable ? `null` tant que la première lecture
 * du coffre (`account_status`) n'est pas revenue — évite d'afficher un instant « connecte
 * un compte » avant de savoir. */
function useAnyAccountLive(): boolean | null {
  const [ready, setReady] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    invoke<StoredStatus>("account_status")
      .then((status) => {
        if (cancelled) return;
        setReady(status.twitch === "live" || status.youtube === "live");
      })
      .catch((error: unknown) => {
        console.error("chat: account_status failed", error);
        if (!cancelled) setReady(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return ready;
}

const FILTERS: Array<{ mode: ChatPlatform | "both"; label: string }> = [
  { mode: "both", label: "Tout" },
  { mode: "twitch", label: "Twitch" },
  { mode: "youtube", label: "YouTube" },
];

export function ChatPanel(_props: IDockviewPanelProps) {
  const accountReady = useAnyAccountLive();
  const { messages, send } = useChat();
  const [filter, setFilter] = useState<ChatPlatform | "both">("both");
  const [draft, setDraft] = useState("");

  if (accountReady === false) {
    return (
      <Panel title="Chat">
        <p className="text-[12.5px] leading-relaxed text-hikari-txt-dim">
          Connecte un compte Twitch ou YouTube (panneau Comptes) pour voir le
          chat ici.
        </p>
      </Panel>
    );
  }

  const visibles = filterChatMessages(messages, filter);

  return (
    <Panel
      title="Chat"
      actions={
        <div className="flex gap-1">
          {FILTERS.map(({ mode, label }) => (
            <button
              key={mode}
              type="button"
              onClick={() => setFilter(mode)}
              className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${
                filter === mode
                  ? "bg-hikari-accent/20 text-hikari-accent"
                  : "text-hikari-txt-faint"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      }
    >
      <div className="flex h-full flex-col gap-2">
        {visibles.length === 0 ? (
          <p className="text-[12.5px] leading-relaxed text-hikari-txt-faint">
            En attente des premiers messages…
          </p>
        ) : (
          <ul className="flex flex-1 flex-col gap-1 overflow-y-auto">
            {visibles.map((message) => (
              <li key={message.id} className="text-[12.5px] leading-snug">
                <span
                  aria-hidden="true"
                  className={
                    message.platform === "twitch"
                      ? "text-hikari-twitch"
                      : "text-hikari-youtube"
                  }
                >
                  ●
                </span>{" "}
                <span className="font-medium text-hikari-txt">
                  {message.username}
                </span>
                <span className="text-hikari-txt-dim">: {message.text}</span>
              </li>
            ))}
          </ul>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const text = draft.trim();
            if (!text) return;
            send(text);
            setDraft("");
          }}
        >
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Répondre sur Twitch…"
            className="w-full rounded-[8px] border border-hikari-line bg-hikari-bg px-2 py-1 text-[12.5px] text-hikari-txt"
          />
        </form>
      </div>
    </Panel>
  );
}
