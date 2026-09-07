// La carte qui porte un écran construit.
//
// Pourquoi elle existe : le Pré-vol et les Paramètres étaient dessinés comme des PANNEAUX
// du cockpit, donc posés par le système de panneaux qui leur donnait leur carte et leur
// titre. Devenus des écrans (Jay, 2026-09-07), ils n'ont plus ce porteur — sans lui, leur
// contenu se collerait au bord de la fenêtre, sans fond ni contour, seul écran de
// l'application à ne pas ressembler aux autres.
//
// Elle reprend exactement la carte de la maquette : fond des cartes, filet, arrondi.

import type { ReactNode } from "react";

interface ScreenFrameProps {
  /** Le nom de l'écran — porté par la région pour un lecteur d'écran, jamais réaffiché :
   * le titre du haut le dit déjà, et l'écrire deux fois mangerait une ligne. */
  label: string;
  children: ReactNode;
}

export function ScreenFrame({ label, children }: ScreenFrameProps) {
  return (
    <section
      aria-label={label}
      className="m-2.5 flex min-h-0 flex-1 flex-col overflow-hidden rounded-hikari border border-hikari-line bg-hikari-bg-2"
    >
      {/* L'écran possède le défilement, et lui seul — même règle que la carte d'un
          panneau. Deux zones qui défilent affichent deux barres côte à côte (vu chez Jay
          le 2026-09-04). */}
      <div className="hikari-scroll min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden">
        {children}
      </div>
    </section>
  );
}
