// Les réglages d'UNE caméra posée dans une scène (2026-09-06).
//
// Ouverts depuis la ligne de la caméra dans le panneau Scènes, comme pour n'importe quelle
// autre source. Ils vivaient dans un panneau à part : ce panneau devait deviner seul quelle
// scène était en direct, et le jour où il a perdu ce fil, les réglages sont devenus
// inatteignables sans qu'aucun test ne bronche (Jay, 2026-09-06).
//
// Ce qu'ils portent : filtres et cadrage.
// Chaque bloc porte le nom de sa caméra comme étiquette de groupe — c'est ce qui permet à
// l'utilisateur, comme à un lecteur d'écran, de savoir de LAQUELLE on parle quand deux
// appareils sont posés dans la même scène.

import { useState } from "react";
import {
  nudgeCamera,
  restartCamera,
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

      {/* Relancer l'appareil, sans rien perdre. Vécu par Jay le 2026-09-07, en plein
      direct : sa caméra a figé, et le seul recours était de la retirer de la scène puis
      de la remettre — donc de refaire son cadrage et ses filtres devant les spectateurs.
      Ce bouton garde tout. */}
      <button
        type="button"
        onClick={() => run("restart", restartCamera(deviceId))}
        disabled={pending === "restart"}
        title="Referme et rouvre l'appareil. Le cadrage et les filtres sont conservés."
        className={`mt-1 ${BUTTON}`}
      >
        {pending === "restart" ? "Relance…" : "Relancer la caméra"}
      </button>

      {/* Pas de « retirer » ici : le ✕ de la ligne de la source le fait, pour toutes les
      sources de la même façon. Deux boutons pour un même geste, c'est un de trop. */}
      {error && <p className="text-hikari-red">❌ {error}</p>}
    </section>
  );
}
