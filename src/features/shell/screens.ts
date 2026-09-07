// Les écrans de Hikari — ce que la barre latérale ouvre.
//
// CE QUE J'AVAIS MAL COMPRIS (Jay, 2026-09-07) : la barre latérale n'ouvre pas des
// panneaux DANS le cockpit. Elle change l'interface entière de droite. « Lorsqu'on est
// sur le cockpit live » est UN écran ; le pré-vol en est un autre, avec un métier
// différent. Le cockpit n'est pas l'application, il en est une pièce.
//
// La maquette le dit dans sa structure : dix sections `.screen`, une seule active à la
// fois, et chaque entrée de la barre latérale en désigne une.

/** Un écran de l'application, tel que la barre latérale y mène. */
export interface Screen {
  id: string;
  /** Ce que la barre latérale affiche, et ce que le titre du haut reprend. */
  label: string;
  /** Construit, ou dessiné et marqué « à venir ». */
  built: boolean;
  /** Ce que l'écran fera, en clair — sert à l'annonce « à venir ». */
  what: string;
}

/** Les écrans, dans l'ordre de la barre latérale (maquette). */
export const SCREENS: Screen[] = [
  {
    id: "home",
    label: "Accueil",
    built: false,
    what: "ton tableau de bord — chiffres clés, derniers streams, ce qui arrive",
  },
  {
    id: "preflight",
    label: "Pré-vol",
    built: true,
    what: "vérifier que tout est prêt avant de lancer",
  },
  {
    id: "cockpit",
    label: "Cockpit Live",
    built: true,
    what: "composer et piloter ton direct",
  },
  {
    id: "edition",
    label: "Édition",
    built: false,
    what: "marqueurs, clips, rediffusion, sous-titres et chapitres",
  },
  {
    id: "publication",
    label: "Publication",
    built: false,
    what: "publier tes vidéos, leur planning, leurs miniatures",
  },
  {
    id: "deck",
    label: "Deck mobile",
    built: false,
    // Cet écran CRÉE les boutons et leurs actions ; le téléphone ne fait que les
    // afficher (Jay, 2026-09-07). Le dire ici évite qu'on le confonde avec le deck
    // lui-même, qui est déjà un panneau du cockpit.
    what: "créer les boutons de ton deck et ce qu'ils déclenchent",
  },
  {
    id: "automations",
    label: "Automations",
    built: false,
    what: "composer tes enchaînements — le moteur existe déjà",
  },
  {
    id: "stats",
    label: "Suivi",
    built: false,
    what: "tes statistiques, la stabilité et tes spectateurs en direct",
  },
  {
    id: "settings",
    label: "Paramètres",
    built: true,
    what: "comptes, périphériques, encodage, appairage, stockage",
  },
];

/** L'écran ouvert au démarrage : le cockpit, comme dans la maquette. */
export const DEFAULT_SCREEN = "cockpit";

/** L'écran d'identifiant `id`, ou celui par défaut si personne ne le connaît.
 *
 * Rend TOUJOURS un écran : une zone principale vide serait le seul état dont l'utilisateur
 * ne pourrait pas sortir — la barre latérale resterait là, mais il ne saurait pas ce qu'il
 * regarde. */
export function screenFor(id: string | null): Screen {
  return (
    SCREENS.find((screen) => screen.id === id) ??
    (SCREENS.find((screen) => screen.id === DEFAULT_SCREEN) as Screen)
  );
}
