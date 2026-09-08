// Ce que la maquette dessine dans le panneau Scènes.
//
// Décision de Jay, 2026-09-05 : dessiner le squelette complet et le marquer « à venir »
// quand une pièce n'est pas encore branchée, plutôt que de laisser des trous.
//
// Un seul élément attend encore sa brique ici :
//   — les COLLECTIONS groupent les scènes par contexte (jeu, interview, pause). Rien ne
//     les porte côté moteur.
// La TRANSITION (fondu au changement de scène, B7) est branchée depuis 2026-09-08 —
// `ScenesPanel` lui passe la durée choisie et le changement.

import { ComingSoon } from "../../components/ui/ComingSoon";
import { TRANSITION_DURATION_LABEL, TRANSITION_DURATIONS_MS } from "./types";

/** Les onglets de collections, tels que la maquette les pose au-dessus des scènes. */
export function SceneCollections() {
  return (
    <ComingSoon block what="grouper tes scènes par collection">
      {/* Une vraie LISTE, pas un `span` portant un rôle : ces onglets forment un ensemble
      ordonné, et un lecteur d'écran annonce alors « liste de 3 éléments ». Le `block` de
      l'enveloppe existe pour ça — une liste dans un `span` serait invalide. */}
      <ul
        aria-label="Collections de scènes"
        className="flex gap-1.5 text-[12px]"
      >
        {/* Les libellés de la maquette, gardés tels quels : ce sont des exemples de ce
        que l'utilisateur écrira, pas des valeurs que l'application invente. */}
        {["LoL", "Interview", "Pause"].map((collection) => (
          <li
            key={collection}
            className="rounded-full border border-hikari-line px-2.5 py-0.5 text-hikari-txt-dim"
          >
            {collection}
          </li>
        ))}
      </ul>
    </ComingSoon>
  );
}

/** La ligne « Transition », en bas du panneau — la durée du fondu appliqué au prochain
 * changement de scène (B7). `value` est TOUJOURS l'une de `TRANSITION_DURATIONS_MS` : le
 * `<select>` n'offre que ces options, donc rien d'autre ne peut en sortir. */
export function SceneTransition({
  value,
  onChange,
}: {
  value: number;
  onChange: (durationMs: number) => void;
}) {
  return (
    <div className="mt-1 border-t border-hikari-line pt-2">
      <label className="flex items-center gap-2 text-[12px] text-hikari-txt-dim">
        🎬 Transition
        <select
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
          className="rounded-[6px] border border-hikari-line bg-hikari-bg px-2 py-0.5 text-hikari-txt"
        >
          {TRANSITION_DURATIONS_MS.map((ms) => (
            <option key={ms} value={ms}>
              {TRANSITION_DURATION_LABEL[ms]}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
