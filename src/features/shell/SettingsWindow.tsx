// Le contenu d'une fenêtre de réglages SÉPARÉE — caméra, texte, et les futures.
//
// Jay, 2026-09-07 : « c'est absolument contre-intuitif. OBS eux-mêmes ne fonctionne pas
// comme ça [...] c'est une fenêtre qui apparaît pour que l'on puisse régler ». Une fenêtre
// native est un objet à l'écran INDÉPENDANT de la fenêtre principale — elle n'a donc pas le
// problème qui obligeait les réglages caméra/texte à vivre repliés sous leur ligne : cette
// contrainte ne vise que ce qui se dessine PAR-DESSUS l'aperçu, dans la MÊME fenêtre.
//
// Cette fenêtre lit ses paramètres dans son URL (posés par `open_settings_window` côté
// Rust) : quelle source, dans quelle scène, avec quel réglage de départ pour les axes que
// le moteur ne rapporte pas lui-même (l'apparence d'un texte).

import { listen } from "@tauri-apps/api/event";
import { useEffect, useState } from "react";
import { CameraControls, type PlacedCamera } from "../camera/CameraControls";
import { TextControls } from "../scenes/TextControls";
import { type TextSettings, withDefaults } from "../scenes/textSettings";
import { emitTextSettingsChanged } from "../scenes/useTextSettings";

/** Les seuls messages moteur que cette fenêtre lit — juste assez pour retrouver l'état
 * ACTUEL de la source qu'elle règle, jamais moins, jamais plus. */
interface SceneListMessage {
  type: "scene_list";
  scenes: {
    name: string;
    sources: {
      name: string;
      target_id: string;
      background_removal: boolean;
      circle_mask: boolean;
    }[];
  }[];
}

function isSceneList(message: unknown): message is SceneListMessage {
  return (
    typeof message === "object" &&
    message !== null &&
    (message as { type?: unknown }).type === "scene_list"
  );
}

/** Ce que la fenêtre principale sait DÉJÀ au moment d'ouvrir la fenêtre de réglages —
 * transmis une fois, à l'ouverture. Le moteur ne rapporte pas l'apparence d'un texte (elle
 * est purement côté application), donc sans ce transport la fenêtre ouvrirait toujours sur
 * les valeurs de départ, jamais sur le dernier réglage choisi. */
interface InitialText {
  text: string;
  settings: TextSettings;
}

export interface SettingsWindowParams {
  kind: "text" | "camera";
  scene: string;
  name: string;
  initial: InitialText | null;
}

/** Lit les paramètres d'ouverture depuis l'URL de la fenêtre. `null` si cette fenêtre n'est
 * pas une fenêtre de réglages — c'est ce que `App.tsx` teste pour décider quoi monter. */
export function readSettingsWindowParams(
  search: string,
): SettingsWindowParams | null {
  const query = new URLSearchParams(search);
  if (query.get("settings") !== "1") return null;

  const kind = query.get("kind");
  const scene = query.get("scene");
  const name = query.get("name");
  if (kind !== "text" && kind !== "camera") return null;
  if (!scene || !name) return null;

  const rawInitial = query.get("initial");
  let initial: InitialText | null = null;
  if (rawInitial) {
    try {
      const parsed = JSON.parse(rawInitial) as Partial<InitialText>;
      if (typeof parsed.text === "string") {
        initial = {
          text: parsed.text,
          settings: withDefaults(parsed.settings),
        };
      }
    } catch {
      // Un JSON illisible retombe sur les valeurs de départ, jamais sur un écran cassé —
      // même principe que `withDefaults` : une donnée absente ou corrompue n'empêche pas
      // de régler la source, elle prive seulement du dernier réglage connu.
      initial = null;
    }
  }
  return { kind, scene, name, initial };
}

export function SettingsWindow({
  kind,
  scene,
  name,
  initial,
}: SettingsWindowParams) {
  const [sourceState, setSourceState] = useState<{
    targetId: string;
    backgroundRemoval: boolean;
    circleMask: boolean;
  } | null>(null);
  const [textSettings, setTextSettings] = useState<TextSettings>(
    initial?.settings ?? withDefaults(undefined),
  );

  // Caméra et texte lisent leur état RÉEL dans le flux du moteur, jamais dans une copie
  // figée à l'ouverture : une autre fenêtre ou le rejeu de session peut avoir changé la
  // source entre-temps, et cette fenêtre doit refléter ce qui EST, pas ce qui était.
  useEffect(() => {
    const unlisten = listen<unknown>("engine-message", (event) => {
      const msg = event.payload;
      if (!isSceneList(msg)) return;
      const found = msg.scenes
        .find((s) => s.name === scene)
        ?.sources.find((s) => s.name === name);
      if (found) {
        setSourceState({
          targetId: found.target_id,
          backgroundRemoval: found.background_removal,
          circleMask: found.circle_mask,
        });
      }
    });
    return () => {
      unlisten.then((f) => f());
    };
  }, [scene, name]);

  return (
    <div className="min-h-screen bg-hikari-canvas p-3 font-hikari text-hikari-txt">
      {kind === "camera" && (
        <CameraCard scene={scene} name={name} live={sourceState} />
      )}
      {kind === "text" && (
        <TextControls
          scene={scene}
          name={name}
          text={sourceState?.targetId ?? initial?.text ?? name}
          settings={textSettings}
          onChange={(next) => {
            setTextSettings(next);
            // La fenêtre principale est la SEULE à retenir l'apparence d'une session à
            // l'autre (voir ScenesPanel). Sans ce signal, régler un texte depuis sa
            // fenêtre séparée s'appliquerait bien au moteur mais s'oublierait au prochain
            // lancement — exactement la famille de défaut fermée le matin même.
            emitTextSettingsChanged({ scene, name, settings: next }).catch(
              (error: unknown) => {
                console.error("settings-window: emit failed", error);
              },
            );
          }}
        />
      )}
    </div>
  );
}

/** Attend le premier rapport du moteur avant d'afficher les réglages caméra : sans lui, un
 * état de départ deviné (tout à faux) s'afficherait un instant avant la vraie valeur — un
 * bouton "Fond transparent" activé qui ne l'est pas encore trompe plus qu'il n'informe. */
function CameraCard({
  scene,
  name,
  live,
}: {
  scene: string;
  name: string;
  live: {
    targetId: string;
    backgroundRemoval: boolean;
    circleMask: boolean;
  } | null;
}) {
  if (!live) {
    return (
      <p className="p-2 text-[12.5px] text-hikari-txt-dim">
        En attente du moteur…
      </p>
    );
  }
  const camera: PlacedCamera = {
    deviceId: live.targetId,
    name,
    backgroundRemoval: live.backgroundRemoval,
    circleMask: live.circleMask,
  };
  return <CameraControls camera={camera} scene={scene} />;
}
