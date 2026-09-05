// Les réglages d'UNE caméra posée dans la scène en direct (2026-09-06).
//
// Extrait du panneau parce qu'il y en a désormais un par caméra : filtres, cadrage, retrait.
// Chaque bloc porte le nom de sa caméra comme étiquette de groupe — c'est ce qui permet à
// l'utilisateur, comme à un lecteur d'écran, de savoir de LAQUELLE on parle quand deux
// appareils sont posés dans la même scène.

import { useState } from "react";
import {
  nudgeCamera,
  removeCameraSource,
  scaleCamera,
  setBackgroundRemoval,
  setCircleMask,
} from "./api";

/** Pas fixe en pixels par clic de flèche — un glissement brut a été écarté (celui de la
 * bibliothèque de panneaux casse en silence dans cette vue web, vécu le 2026-07-23). */
const NUDGE_STEP = 40;

/** Une caméra posée dans une scène, telle que le moteur la décrit. */
export interface PlacedCamera {
  deviceId: string;
  name: string;
  backgroundRemoval: boolean;
  circleMask: boolean;
}

interface Props {
  camera: PlacedCamera;
  scene: string;
}

const BUTTON =
  "rounded-[8px] border border-hikari-line px-3 py-1 text-[12.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt disabled:cursor-not-allowed disabled:opacity-50";

const BUTTON_ON =
  "rounded-[8px] border border-hikari-accent px-3 py-1 text-[12.5px] text-hikari-accent transition disabled:cursor-not-allowed disabled:opacity-50";

export function CameraControls({ camera, scene }: Props) {
  // L'état voulu vient du moteur (`camera`). Ce qui vit ici est seulement ce que le moteur
  // ne peut pas dire : un envoi en cours, et l'erreur du dernier geste.
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = (label: string, action: Promise<void>) => {
    setPending(label);
    setError(null);
    action
      .catch((cause: unknown) => setError(String(cause)))
      .finally(() => setPending(null));
  };

  const { deviceId, name, backgroundRemoval, circleMask } = camera;

  return (
    <section
      aria-label={`Réglages de ${name}`}
      className="flex flex-col items-center gap-2 rounded-[10px] border border-hikari-line p-3"
    >
      <p className="text-[12.5px] text-hikari-txt">{name}</p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() =>
            run(
              "background",
              setBackgroundRemoval(deviceId, scene, !backgroundRemoval),
            )
          }
          disabled={pending === "background"}
          className={backgroundRemoval ? BUTTON_ON : BUTTON}
        >
          {backgroundRemoval ? "Fond IA activé ✓" : "Activer fond IA"}
        </button>
        <button
          type="button"
          onClick={() =>
            run("mask", setCircleMask(deviceId, scene, !circleMask))
          }
          disabled={pending === "mask"}
          className={circleMask ? BUTTON_ON : BUTTON}
        >
          {circleMask ? "Masque cercle activé ✓" : "Activer masque cercle"}
        </button>
      </div>

      <p className="text-[12px] text-hikari-txt-faint">
        Position et taille dans cette scène
      </p>
      <div className="grid grid-cols-3 gap-1">
        <span />
        <button
          type="button"
          aria-label="Déplacer vers le haut"
          onClick={() =>
            run("move", nudgeCamera(deviceId, scene, 0, -NUDGE_STEP))
          }
          className={BUTTON}
        >
          ↑
        </button>
        <span />
        <button
          type="button"
          aria-label="Déplacer vers la gauche"
          onClick={() =>
            run("move", nudgeCamera(deviceId, scene, -NUDGE_STEP, 0))
          }
          className={BUTTON}
        >
          ←
        </button>
        <button
          type="button"
          aria-label="Déplacer vers le bas"
          onClick={() =>
            run("move", nudgeCamera(deviceId, scene, 0, NUDGE_STEP))
          }
          className={BUTTON}
        >
          ↓
        </button>
        <button
          type="button"
          aria-label="Déplacer vers la droite"
          onClick={() =>
            run("move", nudgeCamera(deviceId, scene, NUDGE_STEP, 0))
          }
          className={BUTTON}
        >
          →
        </button>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => run("zoom", scaleCamera(deviceId, scene, false))}
          className={BUTTON}
        >
          Réduire −
        </button>
        <button
          type="button"
          onClick={() => run("zoom", scaleCamera(deviceId, scene, true))}
          className={BUTTON}
        >
          Agrandir +
        </button>
      </div>

      <button
        type="button"
        onClick={() => run("remove", removeCameraSource(deviceId, scene))}
        disabled={pending === "remove"}
        className="mt-1 rounded-[8px] border border-hikari-red/60 px-3 py-1 text-[12.5px] text-hikari-red transition hover:bg-hikari-red/10 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {pending === "remove" ? "Retrait…" : "Retirer cette caméra"}
      </button>

      {error && <p className="text-hikari-red">❌ {error}</p>}
    </section>
  );
}
