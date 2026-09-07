// Panneau "Comptes" — première brique visible du cockpit (B-shell). Reprend telle quelle
// la logique déjà vue et testée par Jay (App.tsx d'origine, connexion Twitch réelle) ;
// aucune nouvelle logique métier, seulement le déplacement dans un panneau dockview.
// Étendu (2026-07-19) pour YouTube : même schéma que Twitch, sans l'étape "code" — la
// redirection Google ne montre rien à saisir, seulement une attente puis connecté/erreur.
//
// Corrigé le 2026-09-07 : l'écran n'avait AUCUNE mémoire. Il repartait de « pas connecté »
// à chaque affichage et ne passait au vert que sur l'événement du moment ; sortir des
// Paramètres puis y revenir effaçait donc la connexion à l'écran, alors que le jeton était
// resté dans le coffre. Il DEMANDE désormais l'état au démarrage (`account_status`).

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useCallback, useEffect, useState } from "react";

type TwitchState =
  | { status: "idle" }
  | { status: "waiting"; verificationUri: string; userCode: string }
  | { status: "connected" }
  | { status: "error"; message: string };

type YouTubeState =
  | { status: "idle" }
  | { status: "waiting"; authorizationUrl?: string }
  | { status: "connected" }
  | { status: "error"; message: string };

/// Lit l'état réel du compte au premier affichage, une seule fois pour les deux
/// plateformes — un seul aller-retour plutôt qu'un par écran (mémoire :
/// une lecture partagée nourrit plusieurs affichages, jamais une boucle par écran).
///
/// Un échec de lecture laisse les deux écrans en « pas connecté », ce qui est la lecture
/// prudente : proposer un bouton de connexion inutile coûte un clic, afficher « connecté »
/// à tort ferait chercher la panne ailleurs.
function useStoredAccounts(
  onKnown: (status: { twitch: boolean; youtube: boolean }) => void,
) {
  useEffect(() => {
    let cancelled = false;
    invoke<{ twitch: boolean; youtube: boolean }>("account_status")
      .then((status) => {
        if (!cancelled) onKnown(status);
      })
      .catch((error: unknown) => {
        console.error("accounts: account_status failed", error);
      });
    return () => {
      cancelled = true;
    };
    // `onKnown` est stable (défini dans le composant parent via useCallback).
  }, [onKnown]);
}

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

  // `useCallback` n'est pas une optimisation ici, c'est la correction d'un défaut : sans
  // elle, cette fonction est recréée à chaque rendu, l'effet qui la reçoit se relance,
  // écrit l'état, provoque un rendu — et la lecture du coffre part en boucle sans fin
  // (mesuré : 95 lectures en 50 ms). `setState` est stable, la liste vide est donc juste.
  const markConnected = useCallback(
    () => setState({ status: "connected" }),
    [],
  );

  return { state, connect, markConnected };
}

function useYouTubeConnection() {
  const [state, setState] = useState<YouTubeState>({ status: "idle" });

  useEffect(() => {
    const unlistenUrl = listen<string>("youtube-url", (event) => {
      setState({ status: "waiting", authorizationUrl: event.payload });
    });
    const unlistenConnected = listen("youtube-connected", () => {
      setState({ status: "connected" });
    });
    const unlistenError = listen<string>("youtube-error", (event) => {
      setState({ status: "error", message: event.payload });
    });

    return () => {
      unlistenUrl.then((f) => f());
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

  // `useCallback` n'est pas une optimisation ici, c'est la correction d'un défaut : sans
  // elle, cette fonction est recréée à chaque rendu, l'effet qui la reçoit se relance,
  // écrit l'état, provoque un rendu — et la lecture du coffre part en boucle sans fin
  // (mesuré : 95 lectures en 50 ms). `setState` est stable, la liste vide est donc juste.
  const markConnected = useCallback(
    () => setState({ status: "connected" }),
    [],
  );

  return { state, connect, markConnected };
}

export function AccountsPanel(_props: IDockviewPanelProps) {
  const twitch = useTwitchConnection();
  const youtube = useYouTubeConnection();

  const applyStoredStatus = useCallback(
    (status: { twitch: boolean; youtube: boolean }) => {
      if (status.twitch) twitch.markConnected();
      if (status.youtube) youtube.markConnected();
    },
    [twitch.markConnected, youtube.markConnected],
  );
  useStoredAccounts(applyStoredStatus);

  return (
    // Même piège flexbox que le panneau Caméra : centrer verticalement rend le haut
    // inatteignable dès que le contenu dépasse (voir `CameraPanel.tsx`, 2026-08-04).
    <div className="flex flex-col gap-6">
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
          <div className="text-sm text-hikari-txt-dim">
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
          <p className="text-hikari-red">❌ {twitch.state.message}</p>
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
          <div className="text-sm text-hikari-txt-dim">
            <p>
              Un navigateur s'est ouvert — s'il ne s'affiche pas, ouvre ce lien
              :
            </p>
            {youtube.state.authorizationUrl && (
              <p className="mt-2 break-all text-hikari-txt-faint">
                {youtube.state.authorizationUrl}
              </p>
            )}
          </div>
        )}
        {youtube.state.status === "connected" && (
          <p className="text-hikari-green">✅ Compte YouTube connecté.</p>
        )}
        {youtube.state.status === "error" && (
          <p className="text-hikari-red">❌ {youtube.state.message}</p>
        )}
      </div>
    </div>
  );
}
