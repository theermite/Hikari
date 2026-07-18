// Hikari — coque applicative (socle B0.3) + première tranche verticale visible (B2b) :
// un bouton réel qui déclenche le flux Twitch déjà prouvé manuellement
// (src-tauri/examples/*_manual_auth.rs). Aucune nouvelle logique métier ici — seulement
// l'appel de la commande Tauri qui expose ce qui existe déjà côté Rust.

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useEffect, useState } from "react";

type ConnectionState =
  | { status: "idle" }
  | { status: "waiting"; verificationUri: string; userCode: string }
  | { status: "connected" }
  | { status: "error"; message: string };

function App() {
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
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-950 text-neutral-100">
      <h1 className="text-3xl font-semibold tracking-tight">Hikari 光</h1>
      <p className="text-neutral-400">
        Cockpit stream open-source — socle B0.3
      </p>

      <button
        type="button"
        onClick={connectTwitch}
        disabled={state.status === "waiting"}
        className="rounded-lg bg-purple-600 px-5 py-2.5 font-medium text-white transition hover:bg-purple-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Connecter Twitch
      </button>

      {state.status === "waiting" && (
        <div className="max-w-md text-center text-sm text-neutral-300">
          <p>Un navigateur s'est ouvert — entre ce code si besoin :</p>
          <p className="mt-2 text-2xl font-mono tracking-widest text-purple-400">
            {state.userCode}
          </p>
          <p className="mt-2 break-all text-neutral-500">
            {state.verificationUri}
          </p>
        </div>
      )}
      {state.status === "connected" && (
        <p className="text-emerald-400">✅ Compte Twitch connecté.</p>
      )}
      {state.status === "error" && (
        <p className="max-w-md text-center text-red-400">❌ {state.message}</p>
      )}
    </main>
  );
}

export default App;
