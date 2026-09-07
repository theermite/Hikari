// La carte « Préparation » de la maquette — ce qu'on regarde AVANT de lancer.
//
// Elle n'apparaît que dans la disposition Préparation, comme dans la maquette
// (`.card.only-setup`). Deux parties :
//   — le kit de marque, qui n'existe pas encore : dessiné et marqué « à venir » ;
//   — « Sources à vérifier », qui existe : chaque point est MESURÉ sur l'état réel du
//     moteur. La maquette en montre trois, inventés. Un point vert qui ne regarde rien
//     serait pire qu'aucun point — il rassurerait sans preuve.
//
// Le bouton « Passer en mode Live » de la maquette est réel : il bascule la disposition.

import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useState } from "react";
import { ComingSoon } from "../../components/ui/ComingSoon";
import { Panel } from "../../components/ui/Panel";
import { requestPreset } from "../shell/panelActions";
import { type CheckState, prepChecks } from "./prepChecks";
import type { EngineMessage, SceneInfo } from "./types";

/** Les couleurs de la maquette : vert pour ce qui va, rouge pour ce qui attend, et un gris
 * pour ce qu'on ne SAIT pas. Le gris est le plus important des trois — c'est celui qui
 * empêche de confondre « pas vérifié » avec « vérifié bon ». */
const PASTILLE: Record<CheckState, string> = {
  ok: "bg-hikari-green/[.16] text-hikari-green",
  attention: "bg-hikari-red/[.16] text-hikari-red",
  inconnu: "bg-hikari-line text-hikari-txt-faint",
};

const SIGNE: Record<CheckState, string> = {
  ok: "✓",
  attention: "!",
  inconnu: "?",
};

/** Les couleurs du kit de marque, telles que la maquette les montre. Ce sont celles de
 * Hikari lui-même : tant que Jay n'a pas défini SA charte, montrer des couleurs inventées
 * lui ferait croire à un réglage qui n'existe pas. */
const CHARTE = ["#f5b642", "#3dc3ff", "#0d1117", "#e6edf3"];

export function PrepPanel(_props: IDockviewPanelProps) {
  const [scenes, setScenes] = useState<SceneInfo[] | null>(null);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "scene_list" && msg.scenes && msg.active) {
        setScenes(msg.scenes);
        setActive(msg.active);
      }
    });
    return () => {
      unlisten.then((f) => f());
    };
  }, []);

  const checks = prepChecks(scenes, active);

  return (
    <Panel title="Préparation">
      <p className="mb-2 text-[11px] uppercase tracking-wider text-hikari-txt-faint">
        Kit de marque
      </p>
      <ComingSoon what="poser tes couleurs et ton logo sur tes alertes et bandeaux">
        <span className="flex gap-2">
          {CHARTE.map((couleur) => (
            <span
              key={couleur}
              style={{ background: couleur }}
              className="h-[30px] w-[30px] rounded-[7px] border border-hikari-line"
            />
          ))}
        </span>
      </ComingSoon>

      <p className="mb-2 mt-4 text-[11px] uppercase tracking-wider text-hikari-txt-faint">
        Sources à vérifier
      </p>
      <ul className="flex flex-col gap-2">
        {checks.map((check) => (
          <li
            key={check.id}
            className="flex items-center gap-3 rounded-hikari-s bg-hikari-bg-3 px-4 py-3"
          >
            <span
              aria-hidden="true"
              className={`grid h-[30px] w-[30px] flex-shrink-0 place-items-center rounded-full text-[15px] font-bold ${PASTILLE[check.state]}`}
            >
              {SIGNE[check.state]}
            </span>
            <span className="flex-1">
              <span className="block text-[14px] font-medium text-hikari-txt">
                {check.label}
              </span>
              {check.fix && (
                <span className="block text-[12.5px] text-hikari-txt-dim">
                  {check.fix}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>

      {/* Le bouton de la maquette, et il marche : il bascule la disposition. C'est le
          geste que la carte prépare — tout le reste de l'écran ne sert qu'à décider s'il
          est temps de le faire. */}
      <button
        type="button"
        onClick={() => requestPreset("live")}
        className="mt-4 w-full rounded-hikari-s bg-hikari-accent px-4 py-2.5 text-[13px] font-semibold text-[#1a1206] transition hover:brightness-110"
      >
        Passer en mode Live →
      </button>
    </Panel>
  );
}
