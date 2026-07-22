// Panneau Caméra (B-cam tranche 1) — détection réelle des webcams disponibles, jamais
// une liste présumée. Ajouter la caméra choisie dans une scène EN DIRECT reste hors
// périmètre : ça dépend du lancement continu du moteur, pas encore câblé au démarrage de
// l'appli (dette séparée, voir PET B1 "Dette restante") — cet écran prouve la détection,
// jamais un ajout de façade.

import type { IDockviewPanelProps } from "dockview-react";
import { useState } from "react";
import { listCameras } from "./api";
import type { CameraDevice } from "./types";

type State =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "done"; devices: CameraDevice[] }
  | { status: "error"; message: string };

export function CameraPanel(_props: IDockviewPanelProps) {
  const [state, setState] = useState<State>({ status: "idle" });

  const detect = () => {
    setState({ status: "checking" });
    listCameras()
      .then((devices) => setState({ status: "done", devices }))
      .catch((error: unknown) => {
        setState({ status: "error", message: String(error) });
      });
  };

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 bg-hikari-bg-3 p-6 text-hikari-txt">
      <button
        type="button"
        onClick={detect}
        disabled={state.status === "checking"}
        className="rounded-[10px] bg-hikari-accent px-5 py-2.5 font-medium text-[#1a1206] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {state.status === "checking" ? "Détection…" : "Détecter mes caméras"}
      </button>

      {state.status === "done" && state.devices.length > 0 && (
        <ul className="max-w-md text-center text-hikari-green">
          {state.devices.map((device) => (
            <li key={device.device_id}>✅ {device.name}</li>
          ))}
        </ul>
      )}
      {state.status === "done" && state.devices.length === 0 && (
        <p className="max-w-md text-center text-hikari-txt-faint">
          Aucune caméra détectée.
        </p>
      )}
      {state.status === "error" && (
        <p className="max-w-md text-center text-hikari-red">
          ❌ {state.message}
        </p>
      )}
    </div>
  );
}
