// Panneau Scènes (multi-scène, tranche 1) — créer des scènes nommées et basculer entre
// elles. Tranche 1 : les scènes créées sont vides (aucune source n'y va encore, voir PET
// B7) ; ce panneau prouve juste création + liste + bascule à l'écran.

import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useState } from "react";
import { createScene, switchScene } from "./api";
import type { EngineMessage } from "./types";

type State =
  | { status: "idle" }
  | { status: "ready"; names: string[]; active: string };

export function ScenesPanel(_props: IDockviewPanelProps) {
  const [state, setState] = useState<State>({ status: "idle" });
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [switchError, setSwitchError] = useState<string | null>(null);

  useEffect(() => {
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "scene_list" && msg.names && msg.active) {
        setState({ status: "ready", names: msg.names, active: msg.active });
      }
    });
    return () => {
      unlisten.then((f) => f());
    };
  }, []);

  const submitCreate = () => {
    const name = newName.trim();
    if (!name) return;
    setCreateError(null);
    createScene(name)
      .then(() => setNewName(""))
      .catch((error: unknown) => setCreateError(String(error)));
  };

  const activate = (name: string) => {
    setSwitchError(null);
    switchScene(name).catch((error: unknown) => setSwitchError(String(error)));
  };

  return (
    <div className="flex h-full flex-col gap-4 bg-hikari-bg-3 p-6 text-hikari-txt">
      <h3 className="text-[12px] uppercase tracking-wider text-hikari-txt-faint">
        Scènes
      </h3>

      {state.status === "idle" && (
        <p className="text-hikari-txt-faint">
          Ouvre le panneau Aperçu pour gérer les scènes.
        </p>
      )}

      {state.status === "ready" && (
        <ul className="flex flex-col gap-2">
          {state.names.map((name) => (
            <li key={name} className="flex items-center justify-between gap-3">
              <span
                className={
                  name === state.active
                    ? "font-medium text-hikari-accent"
                    : "text-hikari-txt"
                }
              >
                {name} {name === state.active && "● en direct"}
              </span>
              <button
                type="button"
                onClick={() => activate(name)}
                disabled={name === state.active}
                className="rounded-[8px] border border-hikari-line px-3 py-1 text-[12.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt disabled:cursor-not-allowed disabled:opacity-50"
              >
                Basculer
              </button>
            </li>
          ))}
        </ul>
      )}

      {switchError && <p className="text-hikari-red">❌ {switchError}</p>}

      <div className="flex gap-2">
        <input
          type="text"
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && submitCreate()}
          placeholder="Nom de la nouvelle scène"
          className="flex-1 rounded-[8px] border border-hikari-line bg-hikari-bg px-3 py-1.5 text-hikari-txt placeholder:text-hikari-txt-faint"
        />
        <button
          type="button"
          onClick={submitCreate}
          disabled={!newName.trim()}
          className="rounded-[8px] bg-hikari-accent px-4 py-1.5 font-medium text-[#1a1206] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Créer
        </button>
      </div>
      {createError && <p className="text-hikari-red">❌ {createError}</p>}
    </div>
  );
}
