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
  // L'onglet du cockpit AFFICHE déjà le nom du panneau. Un second titre juste en dessous
  // répétait le même mot et mangeait une ligne sur chacun des six panneaux (vu à l'écran
  // 2026-09-04). Le nom part donc dans `aria-label` — un lecteur d'écran nomme toujours la
  // région, l'œil ne lit plus deux fois. L'en-tête ne s'affiche que s'il porte autre chose.
  const hasHeader = Boolean(badge || actions);

  return (
    <section
      aria-label={title}
      className="flex h-full flex-col overflow-hidden bg-hikari-bg-2"
    >
      {hasHeader ? (
        <header className="flex flex-shrink-0 items-center gap-2 border-b border-hikari-line px-3 py-1.5">
          {badge ? <Badge>{badge}</Badge> : null}
          {actions ? (
            <div className="ml-auto flex items-center gap-1">{actions}</div>
          ) : null}
        </header>
      ) : null}
      {/* LA carte possède le défilement, et elle est la seule. Un contenu qui défile aussi
          affiche deux barres côte à côte — vu sur l'écran de Jay le 2026-09-04, dès la
          première migration. Un panneau migré retire donc son propre `overflow`. */}
      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden p-3">
        {children}
      </div>
    </section>
  );
}
