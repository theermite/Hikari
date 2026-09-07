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
  | { status: "connected"; account?: string }
  | { status: "error"; message: string };

type YouTubeState =
  | { status: "idle" }
  | { status: "waiting"; authorizationUrl?: string }
  | { status: "connected"; account?: string }
  | { status: "error"; message: string };

/// Lit l'état réel du compte au premier affichage, une seule fois pour les deux
/// plateformes — un seul aller-retour plutôt qu'un par écran (mémoire :
/// une lecture partagée nourrit plusieurs affichages, jamais une boucle par écran).
///
/// Un échec de lecture laisse les deux écrans en « pas connecté », ce qui est la lecture
/// prudente : proposer un bouton de connexion inutile coûte un clic, afficher « connecté »
/// à tort ferait chercher la panne ailleurs.
// Les marques des plateformes, groupees ici pour qu'une couleur ne soit ecrite qu'UNE
// fois : deux boutons violets ecrits a deux endroits finissent par diverger.
//
// Les logos sont marques `aria-hidden` : le nom du bouton se lit sans eux, le logo ne fait
// que le confirmer. Un lecteur d'ecran annonce donc « Connecter Twitch », pas une image.
const TWITCH_LOGO = (
  <svg
    aria-hidden="true"
    viewBox="0 0 24 24"
    className="h-4 w-4 shrink-0 fill-current"
  >
    <path d="M3.7 0 1.2 4.5v15.9h5.4V24h3l3-3.6h4.4L24 14.3V0H3.7Zm2.1 2.1h16.1v11.1l-3 3h-4.9l-3 3v-3H5.8V2.1Z" />
    <path d="M11 6.4h2.1v5.9H11V6.4Zm5.4 0h2.1v5.9h-2.1V6.4Z" />
  </svg>
);

const YOUTUBE_LOGO = (
  <svg
    aria-hidden="true"
    viewBox="0 0 24 24"
    className="h-4 w-4 shrink-0 fill-current"
  >
    <path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2 31.3 31.3 0 0 0 0 12a31.3 31.3 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1A31.3 31.3 0 0 0 24 12a31.3 31.3 0 0 0-.5-5.8ZM9.6 15.6V8.4l6.3 3.6-6.3 3.6Z" />
  </svg>
);

// La classe de couleur porte le NOM de la plateforme et non sa valeur : c'est ce que le
// test verifie, et c'est ce qui empeche un violet ecrit deux fois de deriver.
const BOUTON_BASE =
  "flex items-center justify-center gap-2 rounded-[10px] px-5 py-2.5 font-medium text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50";

// Le nom du compte, quand on le connait — jamais un nom invente.
//
// Se taire est ici la reponse honnete : un compte connecte avant que ce champ n'existe n'en
// porte pas, et afficher « compte principal » ferait lancer un direct sur la foi d'un nom
// que personne n'a lu chez la plateforme.
function CompteConnecte({
  plateforme,
  nom,
}: {
  plateforme: string;
  nom?: string;
}) {
  return (
    <p className="text-hikari-green">
      ✅ Compte {plateforme} connecté
      {nom ? <span className="font-medium"> — {nom}</span> : null}.
    </p>
  );
}

interface StoredStatus {
  twitch: boolean;
  youtube: boolean;
  twitch_account?: string | null;
  youtube_account?: string | null;
}

function useStoredAccounts(onKnown: (status: StoredStatus) => void) {
  useEffect(() => {
    let cancelled = false;
    invoke<StoredStatus>("account_status")
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
    (account?: string) => setState({ status: "connected", account }),
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
    (account?: string) => setState({ status: "connected", account }),
    [],
  );

  return { state, connect, markConnected };
}

export function AccountsPanel(_props: IDockviewPanelProps) {
  const twitch = useTwitchConnection();
  const youtube = useYouTubeConnection();

  const applyStoredStatus = useCallback(
    (status: StoredStatus) => {
      if (status.twitch)
        twitch.markConnected(status.twitch_account ?? undefined);
      if (status.youtube)
        youtube.markConnected(status.youtube_account ?? undefined);
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
          className={`${BOUTON_BASE} bg-hikari-twitch`}
        >
          {TWITCH_LOGO}
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
          <CompteConnecte plateforme="Twitch" nom={twitch.state.account} />
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
          className={`${BOUTON_BASE} bg-hikari-youtube`}
        >
          {YOUTUBE_LOGO}
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
          <CompteConnecte plateforme="YouTube" nom={youtube.state.account} />
        )}
        {youtube.state.status === "error" && (
          <p className="text-hikari-red">❌ {youtube.state.message}</p>
        )}
      </div>
    </div>
  );
}
