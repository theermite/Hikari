// Barre latérale — structure de navigation reprise de la maquette validée
// (docs/Mockup-Hikari-Stream.html, #sidebar). "Cockpit Live" et "Pré-vol" mènent à un
// écran réel ; les autres entrées existent dans la maquette mais leurs écrans ne sont pas
// construits — affichées désactivées avec un repère "bientôt" (jamais un lien mort
// silencieux, Dignity).

interface NavItem {
  label: string;
  built: boolean;
  /** L'ÉCRAN que cette entrée ouvre. La barre latérale change toute l'interface de
   * droite, elle n'ouvre pas un panneau dans le cockpit (Jay, 2026-09-07). */
  screenId?: string;
  icon: NavIconName;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

// Chaque entrée mène à un ÉCRAN, y compris celles qui ne sont pas construites : elles
// ouvrent leur place, marquée « à venir », au lieu de ne rien faire. Un bouton mort
// laisse croire à une panne ; un écran annoncé renseigne.
const NAV_GROUPS: NavGroup[] = [
  {
    label: "",
    items: [{ label: "Accueil", built: false, screenId: "home", icon: "home" }],
  },
  {
    label: "Diffuser",
    items: [
      { label: "Pré-vol", built: true, screenId: "preflight", icon: "prevol" },
      {
        label: "Cockpit Live",
        built: true,
        screenId: "cockpit",
        icon: "cockpit",
      },
    ],
  },
  {
    label: "Produire",
    items: [
      { label: "Édition", built: false, screenId: "edition", icon: "edition" },
      {
        label: "Publication",
        built: false,
        screenId: "publication",
        icon: "publication",
      },
      { label: "Deck mobile", built: false, screenId: "deck", icon: "deck" },
      {
        label: "Automations",
        built: false,
        screenId: "automations",
        icon: "automations",
      },
    ],
  },
  {
    label: "Suivre",
    items: [{ label: "Suivi", built: false, screenId: "stats", icon: "suivi" }],
  },
  {
    label: "Système",
    items: [
      {
        label: "Paramètres",
        built: true,
        screenId: "settings",
        icon: "parametres",
      },
    ],
  },
];

interface SidebarProps {
  /** Ouvre l'écran demandé. La zone de droite change ENTIÈREMENT — le cockpit est un
   * écran parmi d'autres, jamais le tout (Jay, 2026-09-07). */
  onOpenScreen?: (screenId: string) => void;
  /** L'écran actuellement ouvert, pour que son entrée se distingue. */
  activeScreen?: string;
}

import { ComingSoon } from "../../components/ui/ComingSoon";
import { Flag } from "./Flag";
import { NAV_ICONS, type NavIconName } from "./NavIcons";

export function Sidebar({ onOpenScreen, activeScreen }: SidebarProps) {
  return (
    // `w-60` = 240 px, la largeur que la maquette fixe en fin de fichier (elle relève sa
    // valeur de 224 à 240). Les entrées les plus longues — « Deck mobile bientôt » — y
    // tiennent sans se serrer.
    <aside className="m-2.5 mr-0 flex w-60 flex-shrink-0 flex-col gap-1 rounded-hikari border border-hikari-line bg-hikari-bg-2 p-3">
      <div className="mb-3 flex items-center gap-2.5 px-1 pb-2 pt-1">
        <div className="grid h-8.5 w-8.5 flex-shrink-0 place-items-center rounded-[9px] bg-[radial-gradient(circle_at_30%_30%,_#f5b642,_#c8891f)] text-[19px] font-extrabold text-[#1a1206]">
          光
        </div>
        <div>
          <div className="text-[17px] font-bold tracking-tight text-hikari-txt">
            Hikari
          </div>
          <div className="text-[11px] text-hikari-txt-faint">
            Stream l'esprit tranquille
          </div>
        </div>
      </div>

      <nav className="flex flex-col gap-2">
        {NAV_GROUPS.map((group) => (
          <div key={group.label || "root"}>
            {group.label && (
              <div className="mb-1 px-2.5 text-[11px] uppercase tracking-wider text-hikari-txt-faint">
                {group.label}
              </div>
            )}
            {group.items.map((item) => {
              const Icon = NAV_ICONS[item.icon];
              return (
                // TOUTES les entrees sont cliquables, y compris celles qui ne sont pas
                // construites : elles ouvrent leur ecran, marque « a venir ». Elles
                // etaient desactivees, donc un clic ne faisait rien — et rien ressemble a
                // une panne. Un ecran qui annonce ce qu'il fera renseigne.
                <button
                  key={item.label}
                  type="button"
                  onClick={() => onOpenScreen?.(item.screenId as string)}
                  aria-current={
                    activeScreen === item.screenId ? "page" : undefined
                  }
                  // Seule l'entree OUVERTE porte l'accent. Avant, toutes les entrees
                  // construites l'avaient : on ne pouvait pas savoir ou l'on etait.
                  className={`flex w-full items-center gap-2.5 rounded-hikari-s px-2.5 py-2.5 text-left text-[13.5px] font-medium transition ${
                    activeScreen === item.screenId
                      ? "bg-hikari-accent/[.14] text-hikari-accent"
                      : "text-hikari-txt-dim hover:bg-hikari-bg-3 hover:text-hikari-txt"
                  }`}
                >
                  <Icon />
                  <span>{item.label}</span>
                  {!item.built && (
                    <span className="ml-auto text-[10px] text-hikari-txt-faint">
                      bientôt
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Le pied de la maquette : langue et Adaptation. Dessinés et MARQUÉS « à venir »
          plutôt qu'absents (Jay, 2026-09-05) — on voit ce qui arrive, et le squelette est
          complet au lieu d'être rapiécé plus tard. */}
      <div className="mt-auto flex gap-2 border-t border-hikari-line pt-3">
        <ComingSoon what="choisir la langue de l'interface">
          <span className="flex items-center gap-1.5 rounded-[7px] border border-hikari-line px-2.5 py-1.5 text-[12.5px] text-hikari-txt-dim">
            <Flag lang="fr" /> FR ▾
          </span>
        </ComingSoon>
        <ComingSoon what="adapter l'affichage à ton confort">
          <span className="flex flex-1 items-center gap-1.5 rounded-[7px] border border-hikari-line px-2.5 py-1.5 text-[12.5px] text-hikari-txt-dim">
            ✨ Adaptation
          </span>
        </ComingSoon>
      </div>
    </aside>
  );
}
