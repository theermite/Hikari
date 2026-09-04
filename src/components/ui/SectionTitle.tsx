// SectionTitle — le petit intitulé en capitales qui ouvre une section dans un panneau
// (« SCÈNES », « AUDIO », « SOURCES »).
//
// C'est un vrai titre, pas un `<div>` stylé : les titres sont ce qui permet de sauter de
// section en section au clavier et au lecteur d'écran. Aujourd'hui les panneaux affichent
// ces mots comme du décor, donc la structure de l'écran n'existe que visuellement.

import type { ReactNode } from "react";

interface SectionTitleProps {
  children: ReactNode;
  /** Niveau de titre. `3` par défaut : une section vit sous le titre du panneau. */
  level?: 3 | 4;
}

export function SectionTitle({ children, level = 3 }: SectionTitleProps) {
  const Tag = `h${level}` as "h3" | "h4";
  return (
    <Tag className="text-[11px] font-semibold uppercase tracking-wider text-hikari-txt-faint">
      {children}
    </Tag>
  );
}
