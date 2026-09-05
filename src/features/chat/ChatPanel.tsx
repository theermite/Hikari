// Panneau Chat — la colonne de droite de la maquette.
//
// Dessiné et MARQUÉ « à venir », jamais absent (décision de Jay, 2026-09-05) : on voit ce
// qui arrive, et le squelette du cockpit est complet au lieu d'être rapiécé plus tard.
//
// Aucun faux message n'est affiché. La maquette en montre pour donner l'idée ; ici, des
// pseudonymes inventés ressembleraient à de vrais spectateurs, et c'est précisément la
// limite à ne pas franchir. Ce que le panneau montre, c'est ce qu'il fera et ce qui lui
// manque pour le faire.

import type { IDockviewPanelProps } from "dockview-react";

import { Panel } from "../../components/ui/Panel";
import { SectionTitle } from "../../components/ui/SectionTitle";

/** Ce que le chat apportera, dans l'ordre où la maquette le montre. */
const PROMESSES = [
  "Les messages de Twitch et YouTube réunis en une seule colonne",
  "Les alertes d'abonnement et de don au fil de la conversation",
  "La modération : masquer un message, bloquer un lien",
] as const;

export function ChatPanel(_props: IDockviewPanelProps) {
  return (
    <Panel title="Chat">
      <div className="flex flex-col gap-4">
        <p className="text-[12.5px] leading-relaxed text-hikari-txt-dim">
          Le chat arrivera ici, à la place que la maquette lui donne. Il attend
          la connexion aux plateformes.
        </p>

        <div className="flex flex-col gap-2">
          <SectionTitle level={4}>Ce qu'il apportera</SectionTitle>
          <ul className="flex flex-col gap-1.5">
            {PROMESSES.map((promesse) => (
              <li
                key={promesse}
                className="flex gap-2 text-[12px] text-hikari-txt-faint"
              >
                <span aria-hidden="true" className="text-hikari-accent">
                  ·
                </span>
                {promesse}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-[11.5px] leading-relaxed text-hikari-txt-faint">
          Aucun message d'exemple n'est affiché : des pseudonymes inventés
          ressembleraient à de vrais spectateurs.
        </p>
      </div>
    </Panel>
  );
}
