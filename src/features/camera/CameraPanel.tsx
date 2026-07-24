// Panneau Caméra (B-cam) — détection réelle des webcams disponibles, jamais une liste
// présumée. Chaque caméra détectée peut être ajoutée comme vraie source dans la scène en
// direct (visible dans le panneau Aperçu) — nécessite que le moteur tourne déjà (Aperçu
// ouvert) ; l'erreur du pont Tauri s'affiche telle quelle sinon, jamais un échec muet.
// Les effets (fond IA, masque cercle) sont de vrais interrupteurs marche/arrêt — chaque
// bascule reconstruit brièvement la caméra côté moteur (bibliothèque sans API de retrait
// de filtre), un clignotement bref assumé et disclosé à Jay (2026-07-23).

import type { IDockviewPanelProps } from "dockview-react";
import { useState } from "react";
import {
  addCameraSource,
  listCameras,
  nudgeCamera,
  removeCameraSource,
  scaleCamera,
  setBackgroundRemoval,
  setCircleMask,
} from "./api";
import type { CameraDevice } from "./types";

/** Fixed pixel step per arrow-button click (B7) — a raw drag was ruled out (dockview's
 * own drag already broke silently in this WebView2 build, session 2026-07-23). */
const NUDGE_STEP = 40;

type State =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "done"; devices: CameraDevice[] }
  | { status: "error"; message: string };

type AddState =
  | { status: "idle" }
  | { status: "adding"; deviceId: string }
  | { status: "added"; deviceId: string }
  | { status: "error"; deviceId: string; message: string };

interface EffectState {
  enabled: boolean;
  pending: boolean;
  error: string | null;
}

type RemoveState =
  | { status: "idle" }
  | { status: "removing" }
  | { status: "error"; message: string };

const INITIAL_EFFECT: EffectState = {
  enabled: false,
  pending: false,
  error: null,
};

export function CameraPanel(_props: IDockviewPanelProps) {
  const [state, setState] = useState<State>({ status: "idle" });
  const [addState, setAddState] = useState<AddState>({ status: "idle" });
  const [backgroundState, setBackgroundState] =
    useState<EffectState>(INITIAL_EFFECT);
  const [maskState, setMaskState] = useState<EffectState>(INITIAL_EFFECT);
  const [removeState, setRemoveState] = useState<RemoveState>({
    status: "idle",
  });
  const [transformError, setTransformError] = useState<string | null>(null);

  const detect = () => {
    setState({ status: "checking" });
    listCameras()
      .then((devices) => setState({ status: "done", devices }))
      .catch((error: unknown) => {
        setState({ status: "error", message: String(error) });
      });
  };

  const addToScene = (deviceId: string) => {
    setAddState({ status: "adding", deviceId });
    addCameraSource(deviceId)
      .then(() => setAddState({ status: "added", deviceId }))
      .catch((error: unknown) => {
        setAddState({ status: "error", deviceId, message: String(error) });
      });
  };

  const toggleBackground = () => {
    const next = !backgroundState.enabled;
    setBackgroundState((s) => ({ ...s, pending: true, error: null }));
    setBackgroundRemoval(next)
      .then(() =>
        setBackgroundState({ enabled: next, pending: false, error: null }),
      )
      .catch((error: unknown) => {
        setBackgroundState((s) => ({
          ...s,
          pending: false,
          error: String(error),
        }));
      });
  };

  const toggleMask = () => {
    const next = !maskState.enabled;
    setMaskState((s) => ({ ...s, pending: true, error: null }));
    setCircleMask(next)
      .then(() => setMaskState({ enabled: next, pending: false, error: null }))
      .catch((error: unknown) => {
        setMaskState((s) => ({ ...s, pending: false, error: String(error) }));
      });
  };

  const move = (dx: number, dy: number) => {
    setTransformError(null);
    nudgeCamera(dx, dy).catch((error: unknown) =>
      setTransformError(String(error)),
    );
  };

  const zoom = (grow: boolean) => {
    setTransformError(null);
    scaleCamera(grow).catch((error: unknown) =>
      setTransformError(String(error)),
    );
  };

  const removeCamera = () => {
    setRemoveState({ status: "removing" });
    removeCameraSource()
      .then(() => {
        // The camera and every filter on it are gone — reset so Jay can add a fresh one.
        setAddState({ status: "idle" });
        setBackgroundState(INITIAL_EFFECT);
        setMaskState(INITIAL_EFFECT);
        setRemoveState({ status: "idle" });
      })
      .catch((error: unknown) => {
        setRemoveState({ status: "error", message: String(error) });
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
        <ul className="flex max-w-md flex-col gap-2">
          {state.devices.map((device) => (
            <li
              key={device.device_id}
              className="flex items-center justify-between gap-3"
            >
              <span className="text-hikari-green">✅ {device.name}</span>
              <button
                type="button"
                onClick={() => addToScene(device.device_id)}
                disabled={
                  addState.status === "adding" &&
                  addState.deviceId === device.device_id
                }
                className="rounded-[8px] border border-hikari-line px-3 py-1 text-[12.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt disabled:cursor-not-allowed disabled:opacity-50"
              >
                {addState.status === "adding" &&
                addState.deviceId === device.device_id
                  ? "Ajout…"
                  : addState.status === "added" &&
                      addState.deviceId === device.device_id
                    ? "Ajoutée ✓"
                    : "Ajouter à la scène"}
              </button>
            </li>
          ))}
        </ul>
      )}
      {addState.status === "added" && (
        <div className="flex max-w-md flex-col items-center gap-2">
          <p className="text-[12px] text-hikari-txt-faint">
            Effets caméra — chaque bascule reconstruit brièvement la caméra
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={toggleBackground}
              disabled={backgroundState.pending}
              className={`rounded-[8px] border px-3 py-1 text-[12.5px] transition disabled:cursor-not-allowed disabled:opacity-50 ${
                backgroundState.enabled
                  ? "border-hikari-accent text-hikari-accent"
                  : "border-hikari-line text-hikari-txt-dim hover:border-hikari-accent hover:text-hikari-txt"
              }`}
            >
              {backgroundState.pending
                ? "…"
                : backgroundState.enabled
                  ? "Fond IA activé ✓"
                  : "Activer fond IA"}
            </button>
            <button
              type="button"
              onClick={toggleMask}
              disabled={maskState.pending}
              className={`rounded-[8px] border px-3 py-1 text-[12.5px] transition disabled:cursor-not-allowed disabled:opacity-50 ${
                maskState.enabled
                  ? "border-hikari-accent text-hikari-accent"
                  : "border-hikari-line text-hikari-txt-dim hover:border-hikari-accent hover:text-hikari-txt"
              }`}
            >
              {maskState.pending
                ? "…"
                : maskState.enabled
                  ? "Masque cercle activé ✓"
                  : "Activer masque cercle"}
            </button>
          </div>
          {backgroundState.error && (
            <p className="text-center text-hikari-red">
              ❌ {backgroundState.error}
            </p>
          )}
          {maskState.error && (
            <p className="text-center text-hikari-red">❌ {maskState.error}</p>
          )}
          <p className="text-[12px] text-hikari-txt-faint">
            Position et taille dans la scène
          </p>
          <div className="grid grid-cols-3 gap-1">
            <span />
            <button
              type="button"
              onClick={() => move(0, -NUDGE_STEP)}
              className="rounded-[8px] border border-hikari-line px-3 py-1 text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
            >
              ↑
            </button>
            <span />
            <button
              type="button"
              onClick={() => move(-NUDGE_STEP, 0)}
              className="rounded-[8px] border border-hikari-line px-3 py-1 text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
            >
              ←
            </button>
            <button
              type="button"
              onClick={() => move(0, NUDGE_STEP)}
              className="rounded-[8px] border border-hikari-line px-3 py-1 text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
            >
              ↓
            </button>
            <button
              type="button"
              onClick={() => move(NUDGE_STEP, 0)}
              className="rounded-[8px] border border-hikari-line px-3 py-1 text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
            >
              →
            </button>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => zoom(false)}
              className="rounded-[8px] border border-hikari-line px-3 py-1 text-[12.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
            >
              Réduire −
            </button>
            <button
              type="button"
              onClick={() => zoom(true)}
              className="rounded-[8px] border border-hikari-line px-3 py-1 text-[12.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
            >
              Agrandir +
            </button>
          </div>
          {transformError && (
            <p className="text-center text-hikari-red">❌ {transformError}</p>
          )}
          <button
            type="button"
            onClick={removeCamera}
            disabled={removeState.status === "removing"}
            className="mt-2 rounded-[8px] border border-hikari-red/60 px-3 py-1 text-[12.5px] text-hikari-red transition hover:bg-hikari-red/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {removeState.status === "removing"
              ? "Retrait…"
              : "Retirer la caméra"}
          </button>
          {removeState.status === "error" && (
            <p className="text-center text-hikari-red">
              ❌ {removeState.message}
            </p>
          )}
        </div>
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
      {addState.status === "error" && (
        <p className="max-w-md text-center text-hikari-red">
          ❌ {addState.message}
        </p>
      )}
    </div>
  );
}
