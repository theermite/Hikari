// Panel — la carte de la maquette : un titre, éventuellement un badge et des actions,
// puis le contenu. C'est la pièce qui fait que deux panneaux se ressemblent.
//
// Ce qu'elle corrige : chaque panneau dessine aujourd'hui son propre en-tête, avec ses
// marges et sa taille de titre. Résultat, des panneaux collés les uns aux autres sans
// rythme commun — le contraire de la maquette, où chaque carte respire pareil.
//
// Le titre est un vrai `<h2>` : c'est ce qui permet de passer de panneau en panneau au
// clavier. Le corps défile seul, pour qu'un panneau long ne pousse jamais son en-tête
// hors de vue.

import type { ReactNode } from "react";
import { Badge } from "./Badge";

interface PanelProps {
  title: string;
  /** Qualifie le panneau d'un mot (« 1 clic », « écoute / diffusion »). */
  badge?: ReactNode;
  /** Boutons alignés à droite de l'en-tête (ajouter, replier…). */
  actions?: ReactNode;
  children: ReactNode;
}

export function Panel({ title, badge, actions, children }: PanelProps) {
  return (
    <section className="flex h-full flex-col overflow-hidden bg-hikari-bg-2">
      <header className="flex flex-shrink-0 items-center gap-2 border-b border-hikari-line px-3 py-2">
        <h2 className="text-[13px] font-semibold text-hikari-txt">{title}</h2>
        {badge ? <Badge>{badge}</Badge> : null}
        {actions ? (
          <div className="ml-auto flex items-center gap-1">{actions}</div>
        ) : null}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">{children}</div>
    </section>
  );
}
