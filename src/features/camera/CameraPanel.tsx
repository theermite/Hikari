// Panneau Caméra (B-cam) — détection réelle des webcams disponibles, jamais une liste
// présumée. Agit sur la scène actuellement en direct (multi-scène tranche 2, Jay
// 2026-07-24) : la caméra est UNE source physique unique, réutilisée dans chaque scène où
// elle apparaît ; ses filtres (fond IA, masque) sont de vrais interrupteurs marche/arrêt
// (`obs_source_set_enabled`, instantané, jamais un rebuild) et gardent un état INDÉPENDANT
// par scène — changer de scène applique automatiquement les filtres de cette scène.
//
// Ce panneau LIT l'état du moteur, il ne le devine pas. Chaque `scene_list` dit, pour la
// scène en direct, si elle porte la caméra et quels filtres y sont actifs : c'est cette
// vérité qui pilote l'affichage. Auparavant le panneau tenait sa propre supposition, remise
// à zéro à chaque changement de scène — après un rejeu de session la caméra était à l'écran
// et le panneau la croyait absente, donc ses filtres restaient hors d'atteinte (Jay,
// 2026-08-06 : « je ne peux pas appliquer des filtres, ce qui est gênant »).

import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { SceneInfo } from "../scenes/types";
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

interface EngineMessage {
  type: string;
  names?: string[];
  active?: string;
  scenes?: SceneInfo[];
}

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
  const [activeScene, setActiveScene] = useState("main");
  const [state, setState] = useState<State>({ status: "idle" });
  const [addState, setAddState] = useState<AddState>({ status: "idle" });
  const [backgroundState, setBackgroundState] =
    useState<EffectState>(INITIAL_EFFECT);
  const [maskState, setMaskState] = useState<EffectState>(INITIAL_EFFECT);
  const [removeState, setRemoveState] = useState<RemoveState>({
    status: "idle",
  });
  const [transformError, setTransformError] = useState<string | null>(null);

  /** Vrai dès qu'une détection a été lancée — la liste des appareils se demande UNE fois,
   * pas à chaque message du moteur. */
  const detecting = useRef(false);

  /** Identité stable : l'écoute des messages du moteur en dépend, et une fonction recréée à
   * chaque rendu la forcerait à se réabonner sans cesse. */
  const detect = useCallback(() => {
    detecting.current = true;
    setState({ status: "checking" });
    listCameras()
      .then((devices) => setState({ status: "done", devices }))
      .catch((error: unknown) => {
        setState({ status: "error", message: String(error) });
      });
  }, []);

  useEffect(() => {
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      // Le moteur vient de démarrer : c'est le premier instant où il peut répondre. Sans
      // cette détection automatique, la liste restait vide tant que l'utilisateur n'avait
      // pas cliqué — et les réglages d'une caméra pourtant visible à l'écran restaient
      // inaccessibles au retour d'une session (Jay, 2026-08-06).
      if (msg.type === "ready" && !detecting.current) detect();

      if (msg.type === "scene_list" && msg.active) {
        setActiveScene(msg.active);
        // Rattrapage si ce panneau a été ouvert APRÈS le démarrage du moteur : il a alors
        // manqué le signal ci-dessus, et rien d'autre ne relancerait la détection.
        if (!detecting.current) detect();

        const live = msg.scenes?.find((scene) => scene.name === msg.active);
        if (!live) return;
        // La scène en direct dit elle-même ce qu'elle porte : on affiche ÇA, jamais une
        // supposition locale. Un réglage en cours d'envoi n'est pas écrasé — sa réponse
        // arrivera dans un `scene_list` suivant.
        const camera = live.sources.find((s) => s.source_kind === "camera");
        setAddState((current) =>
          current.status === "adding"
            ? current
            : camera
              ? { status: "added", deviceId: camera.target_id }
              : { status: "idle" },
        );
        setBackgroundState((current) =>
          current.pending
            ? current
            : { enabled: live.background_removal, pending: false, error: null },
        );
        setMaskState((current) =>
          current.pending
            ? current
            : { enabled: live.circle_mask, pending: false, error: null },
        );
      }
    });
    return () => {
      unlisten.then((f) => f());
    };
  }, [detect]);

  const addToScene = (deviceId: string) => {
    setAddState({ status: "adding", deviceId });
    addCameraSource(deviceId, activeScene)
      .then(() => setAddState({ status: "added", deviceId }))
      .catch((error: unknown) => {
        setAddState({ status: "error", deviceId, message: String(error) });
      });
  };

  const toggleBackground = () => {
    const next = !backgroundState.enabled;
    setBackgroundState((s) => ({ ...s, pending: true, error: null }));
    setBackgroundRemoval(activeScene, next)
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
    setCircleMask(activeScene, next)
      .then(() => setMaskState({ enabled: next, pending: false, error: null }))
      .catch((error: unknown) => {
        setMaskState((s) => ({ ...s, pending: false, error: String(error) }));
      });
  };

  const move = (dx: number, dy: number) => {
    setTransformError(null);
    nudgeCamera(activeScene, dx, dy).catch((error: unknown) =>
      setTransformError(String(error)),
    );
  };

  const zoom = (grow: boolean) => {
    setTransformError(null);
    scaleCamera(activeScene, grow).catch((error: unknown) =>
      setTransformError(String(error)),
    );
  };

  const removeCamera = () => {
    setRemoveState({ status: "removing" });
    removeCameraSource(activeScene)
      .then(() => {
        // The camera and every filter on it are gone FOR THIS SCENE — reset so Jay can add
        // a fresh one.
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
    // `justify-start` + `overflow-y-auto` volontairement, jamais `justify-center` :
    // centrer un contenu plus haut que le panneau rogne le HAUT et ce haut est
    // inatteignable au défilement (piège flexbox connu). Vécu ici — les réglages sous la
    // caméra étaient invisibles dans un panneau latéral étroit (Jay, 2026-08-04).
    <div className="flex h-full flex-col items-center justify-start gap-6 overflow-y-auto bg-hikari-bg-3 p-6 text-hikari-txt">
      <p className="text-[12px] text-hikari-txt-faint">
        Scène : <span className="text-hikari-accent">{activeScene}</span>
      </p>
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
            Effets caméra — propres à cette scène
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
            Position et taille dans cette scène
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
