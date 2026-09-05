// Panneau Caméra (B-cam) — détection réelle des webcams disponibles, jamais une liste
// présumée. Agit sur la scène actuellement en direct.
//
// PLUSIEURS caméras depuis le 2026-09-06. Chaque appareil posé dans la scène a son propre
// bloc de réglages : ses filtres, son cadrage, son retrait. Avant, un seul appareil pouvait
// être ouvert, et en choisir un second renvoyait le premier sans le dire.
//
// Ce panneau LIT l'état du moteur, il ne le devine pas. Chaque `scene_list` dit, pour la
// scène en direct, quelles caméras elle porte et quels filtres y sont actifs : c'est cette
// vérité qui pilote l'affichage. Auparavant le panneau tenait sa propre supposition, remise
// à zéro à chaque changement de scène — après un rejeu de session la caméra était à l'écran
// et le panneau la croyait absente, donc ses filtres restaient hors d'atteinte (Jay,
// 2026-08-06 : « je ne peux pas appliquer des filtres, ce qui est gênant »).

import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Panel } from "../../components/ui/Panel";
import type { SceneInfo } from "../scenes/types";
import { addCameraSource, listCameras } from "./api";
import { CameraControls, type PlacedCamera } from "./CameraControls";
import type { CameraDevice } from "./types";

interface EngineMessage {
  type: string;
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
  | { status: "error"; deviceId: string; message: string };

/** Les caméras que la scène en direct montre, telles que le moteur les décrit. */
function camerasOf(scene: SceneInfo | undefined): PlacedCamera[] {
  if (!scene) return [];
  return scene.sources
    .filter((source) => source.source_kind === "camera")
    .map((source) => ({
      deviceId: source.target_id,
      name: source.name,
      backgroundRemoval: source.background_removal,
      circleMask: source.circle_mask,
    }));
}

export function CameraPanel(_props: IDockviewPanelProps) {
  const [activeScene, setActiveScene] = useState("main");
  const [state, setState] = useState<State>({ status: "idle" });
  const [addState, setAddState] = useState<AddState>({ status: "idle" });
  const [placed, setPlaced] = useState<PlacedCamera[]>([]);

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
        if (live) setPlaced(camerasOf(live));
      }
    });
    return () => {
      unlisten.then((f) => f());
    };
  }, [detect]);

  const addToScene = (deviceId: string) => {
    setAddState({ status: "adding", deviceId });
    addCameraSource(deviceId, activeScene)
      // La confirmation vient du `scene_list` qui suit, jamais de cette promesse : c'est le
      // moteur qui dit ce que la scène porte, et lui seul.
      .then(() => setAddState({ status: "idle" }))
      .catch((error: unknown) => {
        setAddState({ status: "error", deviceId, message: String(error) });
      });
  };

  // Un appareil déjà posé n'est pas reproposé : le rajouter n'ouvrirait rien de neuf.
  const addable =
    state.status === "done"
      ? state.devices.filter(
          (device) =>
            !placed.some((camera) => camera.deviceId === device.device_id),
        )
      : [];

  return (
    // `justify-start` + `overflow-y-auto` volontairement, jamais `justify-center` :
    // centrer un contenu plus haut que le panneau rogne le HAUT et ce haut est
    // inatteignable au défilement (piège flexbox connu). Vécu ici — les réglages sous la
    // caméra étaient invisibles dans un panneau latéral étroit (Jay, 2026-08-04).
    <Panel title="Caméra">
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

      {addable.length > 0 && (
        <ul className="flex flex-col gap-2">
          {addable.map((device) => (
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
                  : "Ajouter à la scène"}
              </button>
            </li>
          ))}
        </ul>
      )}

      {placed.length > 0 && (
        <>
          <p className="text-[12px] text-hikari-txt-faint">
            Caméras de cette scène — chacune a ses propres réglages
          </p>
          {placed.map((camera) => (
            <CameraControls
              key={camera.deviceId}
              camera={camera}
              scene={activeScene}
            />
          ))}
        </>
      )}

      {state.status === "done" && state.devices.length === 0 && (
        <p className="text-hikari-txt-faint">Aucune caméra détectée.</p>
      )}
      {state.status === "done" &&
        state.devices.length > 0 &&
        addable.length === 0 && (
          <p className="text-[12px] text-hikari-txt-faint">
            Toutes tes caméras sont déjà dans cette scène.
          </p>
        )}
      {state.status === "error" && (
        <p className="text-hikari-red">❌ {state.message}</p>
      )}
      {addState.status === "error" && (
        <p className="text-hikari-red">❌ {addState.message}</p>
      )}
    </Panel>
  );
}
