// Panneau "Comptes" — première brique visible du cockpit (B-shell). Reprend telle quelle
// la logique déjà vue et testée par Jay (App.tsx d'origine, connexion Twitch réelle) ;
// aucune nouvelle logique métier, seulement le déplacement dans un panneau dockview.

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useState } from "react";

type ConnectionState =
  | { status: "idle" }
  | { status: "waiting"; verificationUri: string; userCode: string }
  | { status: "connected" }
  | { status: "error"; message: string };

export function TwitchConnectPanel(_props: IDockviewPanelProps) {
  const [state, setState] = useState<ConnectionState>({ status: "idle" });

  useEffect(() => {
    const unlistenCode = listen<{
      verification_uri: string;
      user_code: string;
    }>("twitch-code", (event) => {
      setState({
        status: "waiting",
        verificationUri: event.payload.verification_uri,
        userCode: event.payload.user_code,
      });
    });
    const unlistenConnected = listen("twitch-connected", () => {
      setState({ status: "connected" });
    });
    const unlistenError = listen<string>("twitch-error", (event) => {
      setState({ status: "error", message: event.payload });
    });

    return () => {
      unlistenCode.then((f) => f());
      unlistenConnected.then((f) => f());
      unlistenError.then((f) => f());
    };
  }, []);

  const connectTwitch = () => {
    setState({ status: "idle" });
    invoke("connect_twitch").catch(() => {
      // L'erreur arrive aussi via l'événement "twitch-error" — pas besoin de la
      // dupliquer ici, l'invocation rejetée est juste le signal que ça s'est arrêté.
    });
  };

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 bg-hikari-bg-3 p-6 text-hikari-txt">
      <button
        type="button"
        onClick={connectTwitch}
        disabled={state.status === "waiting"}
        className="rounded-[10px] bg-hikari-accent px-5 py-2.5 font-medium text-[#1a1206] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Connecter Twitch
      </button>

      {state.status === "waiting" && (
        <div className="max-w-md text-center text-sm text-hikari-txt-dim">
          <p>Un navigateur s'est ouvert — entre ce code si besoin :</p>
          <p className="mt-2 font-mono text-2xl tracking-widest text-hikari-accent">
            {state.userCode}
          </p>
          <p className="mt-2 break-all text-hikari-txt-faint">
            {state.verificationUri}
          </p>
        </div>
      )}
      {state.status === "connected" && (
        <p className="text-hikari-green">✅ Compte Twitch connecté.</p>
      )}
      {state.status === "error" && (
        <p className="max-w-md text-center text-hikari-red">
          ❌ {state.message}
        </p>
      )}
    </div>
  );
}
