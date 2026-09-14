// Panneau Chat — lecture fusionnée Twitch + YouTube, filtre par plateforme, réponse et
// modération inline sur Twitch (mise en sourdine, bannissement), épingler (purement
// local, les deux plateformes). Auto-modération, alertes, bandeaux et objectifs restent
// hors de cette partie (voir le découpage convenu avec Jay, 2026-09-14) — le panneau ne
// les promet plus tant qu'ils ne sont pas construits (Dignity : jamais un bouton qui
// prétend faire quelque chose qu'il ne fait pas).

import { invoke } from "@tauri-apps/api/core";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useState } from "react";

import { Panel } from "../../components/ui/Panel";
import { banChatUser, timeoutChatUser } from "./api";
import { filterChatMessages, togglePinned } from "./history";
import type { ChatPlatform, DisplayedChatMessage } from "./types";
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

// Une seule durée, volontairement : la maquette ne demande pas un réglage fin, et un
// choix unique reste lisible d'un coup d'œil pendant un direct. 10 minutes — l'usage
// courant chez les streamers Twitch pour calmer un message sans bannir.
const TIMEOUT_DURATION_SECS = 600;

function moderationHandlers(refreshError: (message: string) => void) {
  return {
    onTimeout: (userId: string) => {
      timeoutChatUser(userId, TIMEOUT_DURATION_SECS).catch((error: unknown) => {
        console.error("chat: chat_timeout_user failed", error);
        refreshError("La mise en sourdine a échoué.");
      });
    },
    onBan: (userId: string) => {
      banChatUser(userId).catch((error: unknown) => {
        console.error("chat: chat_ban_user failed", error);
        refreshError("Le bannissement a échoué.");
      });
    },
  };
}

function MessageRow({
  message,
  pinned,
  onTogglePin,
  onTimeout,
  onBan,
}: {
  message: DisplayedChatMessage;
  pinned: boolean;
  onTogglePin: () => void;
  onTimeout: () => void;
  onBan: () => void;
}) {
  const canModerate = message.platform === "twitch" && message.user_id;

  return (
    <li className="flex items-start justify-between gap-2 text-[12.5px] leading-snug">
      <p className="min-w-0 flex-1">
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
        <span className="font-medium text-hikari-txt">{message.username}</span>
        <span className="text-hikari-txt-dim">: {message.text}</span>
      </p>
      <div className="flex shrink-0 gap-1">
        <button
          type="button"
          onClick={onTogglePin}
          title={pinned ? "Désépingler" : "Épingler"}
          aria-pressed={pinned}
          className={`text-[11px] ${pinned ? "text-hikari-accent" : "text-hikari-txt-faint"}`}
        >
          📌
        </button>
        {canModerate ? (
          <>
            <button
              type="button"
              onClick={onTimeout}
              title="Mettre en sourdine 10 min"
              className="text-[11px] text-hikari-txt-faint hover:text-hikari-accent"
            >
              🔇
            </button>
            <button
              type="button"
              onClick={onBan}
              title="Bannir"
              className="text-[11px] text-hikari-txt-faint hover:text-hikari-red"
            >
              ⛔
            </button>
          </>
        ) : null}
      </div>
    </li>
  );
}

export function ChatPanel(_props: IDockviewPanelProps) {
  const accountReady = useAnyAccountLive();
  const { messages, send } = useChat();
  const [filter, setFilter] = useState<ChatPlatform | "both">("both");
  const [draft, setDraft] = useState("");
  const [pinnedIds, setPinnedIds] = useState<Set<number>>(new Set());
  const [moderationError, setModerationError] = useState<string | null>(null);

  const { onTimeout, onBan } = moderationHandlers(setModerationError);
  const togglePin = (id: number) =>
    setPinnedIds((current) => togglePinned(current, id));

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
  const pinnedMessages = messages.filter((message) =>
    pinnedIds.has(message.id),
  );

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
        {moderationError ? (
          <p className="text-[11.5px] text-hikari-red">{moderationError}</p>
        ) : null}

        {pinnedMessages.length > 0 ? (
          <ul className="flex flex-col gap-1 border-b border-hikari-line pb-2">
            {pinnedMessages.map((message) => (
              <MessageRow
                key={message.id}
                message={message}
                pinned
                onTogglePin={() => togglePin(message.id)}
                onTimeout={() => message.user_id && onTimeout(message.user_id)}
                onBan={() => message.user_id && onBan(message.user_id)}
              />
            ))}
          </ul>
        ) : null}

        {visibles.length === 0 ? (
          <p className="text-[12.5px] leading-relaxed text-hikari-txt-faint">
            En attente des premiers messages…
          </p>
        ) : (
          <ul className="flex flex-1 flex-col gap-1 overflow-y-auto">
            {visibles.map((message) => (
              <MessageRow
                key={message.id}
                message={message}
                pinned={pinnedIds.has(message.id)}
                onTogglePin={() => togglePin(message.id)}
                onTimeout={() => message.user_id && onTimeout(message.user_id)}
                onBan={() => message.user_id && onBan(message.user_id)}
              />
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
