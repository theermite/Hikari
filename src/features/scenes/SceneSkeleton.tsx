// Ce que la maquette dessine dans le panneau Scènes et qui n'est pas encore branché.
//
// Décision de Jay, 2026-09-05 : dessiner le squelette complet et le marquer « à venir »,
// plutôt que de laisser des trous. Trois raisons qu'il donne — on sait ce qui arrive, on
// voit à quoi ça ressemblera, et le squelette tient debout au lieu d'être rapiécé brique
// après brique.
//
// Les deux éléments d'ici attendent leur brique :
//   — les COLLECTIONS groupent les scènes par contexte (jeu, interview, pause). Rien ne
//     les porte côté moteur ;
//   — la TRANSITION choisit ce qui se passe entre deux scènes. C'est la brique qui suit
//     les automations dans l'ordre de travail de Jay.
//
// Tous deux passent par `ComingSoon`, la seule façon autorisée de dire « ça arrive » :
// si chaque écran inventait la sienne, l'utilisateur devrait deviner lesquelles sont des
// promesses.

import { ComingSoon } from "../../components/ui/ComingSoon";

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

/** La ligne « Transition », en bas du panneau, comme dans la maquette. */
export function SceneTransition() {
  return (
    <div className="mt-1 border-t border-hikari-line pt-2">
      <ComingSoon what="choisir la transition entre deux scènes">
        <span className="flex items-center gap-2 text-[12px] text-hikari-txt-dim">
          🎬 Transition
          <span className="rounded-[6px] border border-hikari-line px-2 py-0.5">
            Fondu <span className="text-hikari-accent">0,3 s</span> ▾
          </span>
        </span>
      </ComingSoon>
    </div>
  );
}
