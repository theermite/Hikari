// Panneau Aperçu (B1 dette payée, tranche 1) — le moteur démarre à l'ouverture de ce
// panneau et s'arrête à sa fermeture (jamais 100% du temps, décision Jay 2026-07-22 : le
// moteur tient des ressources GPU/capture). L'image réelle greffée dans ce panneau est
// une brique séparée (positionner une fenêtre native dans un panneau qui bouge/redimensionne,
// un problème différent du cycle de vie) — cet écran affiche le STATUT réel du moteur,
// jamais une image de façade.

import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useState } from "react";
import { startEngine, stopEngine } from "./api";
import type { EngineMessage } from "./types";

type State =
  | { status: "starting" }
  | { status: "ready" }
  | { status: "scene"; sources: string[] }
  | { status: "error"; message: string }
  | { status: "stopped" };

export function PreviewPanel(_props: IDockviewPanelProps) {
  const [state, setState] = useState<State>({ status: "starting" });

  useEffect(() => {
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "ready") {
        setState({ status: "ready" });
      } else if (msg.type === "sources" && msg.items) {
        setState({
          status: "scene",
          sources: msg.items.map((item) => item.name),
        });
      } else if (msg.type === "error" && msg.message) {
        setState({ status: "error", message: msg.message });
      } else if (msg.type === "stopped") {
        setState({ status: "stopped" });
      }
    });

    startEngine().catch((error: unknown) => {
      setState({ status: "error", message: String(error) });
    });

    return () => {
      unlisten.then((f) => f());
      stopEngine().catch((error: unknown) => {
        console.error("preview: stop_engine failed", error);
      });
    };
  }, []);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 bg-hikari-bg-3 p-6 text-center text-hikari-txt">
      {state.status === "starting" && (
        <p className="text-hikari-txt-faint">Démarrage du moteur…</p>
      )}
      {state.status === "ready" && (
        <p className="text-hikari-txt-faint">
          Moteur prêt — en attente de la scène.
        </p>
      )}
      {state.status === "scene" && (
        <p className="text-hikari-green">
          ✅ Scène active : {state.sources.join(", ")}
        </p>
      )}
      {state.status === "error" && (
        <p className="text-hikari-red">❌ {state.message}</p>
      )}
      {state.status === "stopped" && (
        <p className="text-hikari-txt-faint">Moteur arrêté.</p>
      )}
    </div>
  );
}
