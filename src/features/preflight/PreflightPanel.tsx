// Panneau Pré-vol (B9, reste) — détection matériel réelle (F-010) + feu vert (F-012),
// jamais présumé (F-003). Le test privé complet (F-011, aperçu vidéo pendant le check)
// reste hors périmètre : l'aperçu continu de l'ingénieur n'est pas encore câblé au
// démarrage de l'appli (dette séparée, voir PET B1 "Dette restante") — cet écran vérifie
// ce qui est réellement détectable aujourd'hui, jamais un résultat de façade.

import type { IDockviewPanelProps } from "dockview-react";
import { useState } from "react";
import { Panel } from "../../components/ui/Panel";
import { runPreflight } from "./api";
import type { PreflightOutcome } from "./types";

type State =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "done"; outcome: PreflightOutcome }
  | { status: "error"; message: string };

export function PreflightPanel(_props: IDockviewPanelProps) {
  const [state, setState] = useState<State>({ status: "idle" });

  const check = () => {
    setState({ status: "checking" });
    runPreflight()
      .then((outcome) => setState({ status: "done", outcome }))
      .catch((error: unknown) => {
        setState({ status: "error", message: String(error) });
      });
  };

  return (
    // Même piège flexbox que le panneau Caméra : centrer verticalement rend le haut
    // inatteignable dès que le contenu dépasse (voir `CameraPanel.tsx`, 2026-08-04).
    <Panel title="Pré-vol">
      <button
        type="button"
        onClick={check}
        disabled={state.status === "checking"}
        className="rounded-[10px] bg-hikari-accent px-5 py-2.5 font-medium text-[#1a1206] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {state.status === "checking"
          ? "Vérification…"
          : "Lancer la vérification"}
      </button>

      {state.status === "done" && state.outcome.ok && (
        <p className="text-hikari-green">
          ✅ Encodeur détecté : {state.outcome.encoder_name} (
          {state.outcome.hardware ? "matériel" : "logiciel"}). Go Live sûr.
        </p>
      )}
      {state.status === "done" && !state.outcome.ok && (
        <p className="text-hikari-red">
          ❌ Go Live bloqué : {state.outcome.reason}
        </p>
      )}
      {state.status === "error" && (
        <p className="text-hikari-red">❌ {state.message}</p>
      )}
    </Panel>
  );
}
