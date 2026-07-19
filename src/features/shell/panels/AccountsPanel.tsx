// Panneau "Comptes" — première brique visible du cockpit (B-shell). Reprend telle quelle
// la logique déjà vue et testée par Jay (App.tsx d'origine, connexion Twitch réelle) ;
// aucune nouvelle logique métier, seulement le déplacement dans un panneau dockview.
// Étendu (2026-07-19) pour YouTube : même schéma que Twitch, sans l'étape "code" — la
// redirection Google ne montre rien à saisir, seulement une attente puis connecté/erreur.

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useState } from "react";

type TwitchState =
  | { status: "idle" }
  | { status: "waiting"; verificationUri: string; userCode: string }
  | { status: "connected" }
  | { status: "error"; message: string };

type YouTubeState =
  | { status: "idle" }
  | { status: "waiting" }
  | { status: "connected" }
  | { status: "error"; message: string };

function useTwitchConnection() {
  const [state, setState] = useState<TwitchState>({ status: "idle" });

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

  const connect = () => {
    setState({ status: "idle" });
    invoke("connect_twitch").catch((error: unknown) => {
      // Le backend émet désormais toujours "twitch-error" avant de rejeter (voir
      // commands.rs) ; ce log couvre le cas résiduel où l'appel Tauri lui-même échoue
      // avant même d'atteindre le Rust — sinon l'écran resterait muet sans rien logguer.
      console.error("accounts: connect_twitch failed", error);
    });
  };

  return { state, connect };
}

function useYouTubeConnection() {
  const [state, setState] = useState<YouTubeState>({ status: "idle" });

  useEffect(() => {
    const unlistenConnected = listen("youtube-connected", () => {
      setState({ status: "connected" });
    });
    const unlistenError = listen<string>("youtube-error", (event) => {
      setState({ status: "error", message: event.payload });
    });

    return () => {
      unlistenConnected.then((f) => f());
      unlistenError.then((f) => f());
    };
  }, []);

  const connect = () => {
    setState({ status: "waiting" });
    invoke("connect_youtube").catch((error: unknown) => {
      // Même logique que Twitch : le backend émet toujours "youtube-error" avant de
      // rejeter ; ce log couvre l'échec de l'appel Tauri lui-même.
      console.error("accounts: connect_youtube failed", error);
    });
  };

  return { state, connect };
}

export function AccountsPanel(_props: IDockviewPanelProps) {
  const twitch = useTwitchConnection();
  const youtube = useYouTubeConnection();

  return (
    <div className="flex h-full flex-col items-center justify-center gap-8 bg-hikari-bg-3 p-6 text-hikari-txt">
      <div className="flex flex-col items-center gap-4">
        <button
          type="button"
          onClick={twitch.connect}
          disabled={twitch.state.status === "waiting"}
          className="rounded-[10px] bg-hikari-accent px-5 py-2.5 font-medium text-[#1a1206] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Connecter Twitch
        </button>

        {twitch.state.status === "waiting" && (
          <div className="max-w-md text-center text-sm text-hikari-txt-dim">
            <p>Un navigateur s'est ouvert — entre ce code si besoin :</p>
            <p className="mt-2 font-mono text-2xl tracking-widest text-hikari-accent">
              {twitch.state.userCode}
            </p>
            <p className="mt-2 break-all text-hikari-txt-faint">
              {twitch.state.verificationUri}
            </p>
          </div>
        )}
        {twitch.state.status === "connected" && (
          <p className="text-hikari-green">✅ Compte Twitch connecté.</p>
        )}
        {twitch.state.status === "error" && (
          <p className="max-w-md text-center text-hikari-red">
            ❌ {twitch.state.message}
          </p>
        )}
      </div>

      <div className="flex flex-col items-center gap-4">
        <button
          type="button"
          onClick={youtube.connect}
          disabled={youtube.state.status === "waiting"}
          className="rounded-[10px] bg-hikari-accent px-5 py-2.5 font-medium text-[#1a1206] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Connecter YouTube
        </button>

        {youtube.state.status === "waiting" && (
          <p className="max-w-md text-center text-sm text-hikari-txt-dim">
            Un navigateur s'est ouvert — autorise Hikari puis reviens ici.
          </p>
        )}
        {youtube.state.status === "connected" && (
          <p className="text-hikari-green">✅ Compte YouTube connecté.</p>
        )}
        {youtube.state.status === "error" && (
          <p className="max-w-md text-center text-hikari-red">
            ❌ {youtube.state.message}
          </p>
        )}
      </div>
    </div>
  );
}
