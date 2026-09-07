// ComingSoon — la façon UNIQUE de dire « cet élément arrive, il ne marche pas encore ».
//
// Décision de Jay, 2026-09-05 : dessiner le squelette complet de la maquette, y compris
// ce qui n'est pas branché, plutôt que de laisser des trous. Trois raisons qu'il donne :
// on sait ce qui arrive, on voit à quoi ça ressemblera, et le squelette tient debout au
// lieu d'être rapiécé au fur et à mesure.
//
// La frontière avec la tromperie est nette, et c'est elle que ce composant garde : un
// bouton qui FAIT SEMBLANT de marcher trompe ; un élément dessiné et MARQUÉ « à venir »
// renseigne. La marque doit donc être impossible à rater, et jamais purement visuelle —
// `aria-disabled` et le titre au survol la portent aussi pour qui n'y voit pas.
//
// Une seule façon de le dire dans toute l'application : si chaque écran inventait la
// sienne, « bientôt », « à venir » et un simple grisé coexisteraient, et l'utilisateur
// devrait deviner lesquels sont des promesses.

import type { ReactNode } from "react";

interface ComingSoonProps {
  /** Ce que l'élément fera, en clair. Complète la phrase « Bientôt : … ». */
  what: string;
  /** Enveloppe de BLOC quand le contenu en est un — une liste, une région.
   *
   * Pourquoi ce réglage existe : l'enveloppe est un `span`, donc seul du contenu en ligne
   * peut y vivre. Un `ul` ou une région y seraient invalides, et le contournement (poser
   * un rôle sur le `span`) déplace le problème sans le régler — un rôle de groupe réclame
   * un vrai élément de groupe. Deux valeurs, jamais plus : le besoin est binaire. */
  block?: boolean;
  children: ReactNode;
}

/** Enveloppe un élément non branché : il se voit, il ne se clique pas, et il le dit. */
export function ComingSoon({ what, block, children }: ComingSoonProps) {
  const shared = {
    "aria-disabled": true as const,
    title: `Bientôt : ${what}`,
  };
  const marque = <span className="sr-only">(à venir)</span>;
  const style =
    "hikari-coming-soon relative cursor-not-allowed items-center opacity-45 [&_*]:pointer-events-none";

  if (block) {
    return (
      <div {...shared} className={`${style} flex`}>
        {children}
        {marque}
      </div>
    );
  }
  return (
    <span {...shared} className={`${style} inline-flex`}>
      {children}
      {marque}
    </span>
  );
}

/** L'étiquette seule, pour coiffer une zone entière plutôt qu'un seul élément. */
export function ComingSoonTag() {
  return (
    <span className="rounded-full border border-hikari-line bg-hikari-bg px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-hikari-txt-faint">
      à venir
    </span>
  );
}
