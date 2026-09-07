// Un écran annoncé mais pas encore construit.
//
// Il occupe TOUTE la zone principale, comme le fera le vrai. C'est la différence avec un
// panneau grisé : ici l'utilisateur voit la place que l'écran prendra, pas un trou.
//
// Décision de Jay du 2026-09-05, appliquée au niveau au-dessus : on dessine le squelette
// complet et on le marque. On sait ce qui arrive, on voit où ça arrivera, et la coque tient
// debout au lieu d'être rapiécée écran après écran.

import { ComingSoonTag } from "../../components/ui/ComingSoon";
import type { Screen } from "./screens";

export function ScreenPlaceholder({ screen }: { screen: Screen }) {
  return (
    <section
      aria-label={screen.label}
      className="m-2.5 flex flex-1 flex-col items-center justify-center gap-3 rounded-hikari border border-hikari-line bg-hikari-bg-2 p-[18px] text-center"
    >
      <div className="flex items-center gap-2">
        <h2 className="text-[15px] font-semibold text-hikari-txt">
          {screen.label}
        </h2>
        <ComingSoonTag />
      </div>
      {/* Ce que l'écran FERA, en clair. Une annonce sans son contenu ne renseigne
          personne — elle fait juste attendre. */}
      <p className="max-w-md text-[13px] text-hikari-txt-dim">
        Cet écran te servira à {screen.what}.
      </p>
      <p className="text-[12px] text-hikari-txt-faint">
        Il n'est pas encore construit. Rien ici ne fait semblant de marcher.
      </p>
    </section>
  );
}
