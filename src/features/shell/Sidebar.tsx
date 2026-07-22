// Barre latérale — structure de navigation reprise de la maquette validée
// (docs/Mockup-Hikari-Stream.html, #sidebar). "Cockpit Live" et "Pré-vol" mènent à un
// écran réel ; les autres entrées existent dans la maquette mais leurs écrans ne sont pas
// construits — affichées désactivées avec un repère "bientôt" (jamais un lien mort
// silencieux, Dignity).

interface NavItem {
  label: string;
  built: boolean;
  panelId?: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  { label: "", items: [{ label: "Accueil", built: false }] },
  {
    label: "Diffuser",
    items: [
      { label: "Pré-vol", built: true, panelId: "preflight" },
      { label: "Cockpit Live", built: true },
    ],
  },
  {
    label: "Produire",
    items: [
      { label: "Édition", built: false },
      { label: "Publication", built: false },
      { label: "Deck mobile", built: false },
      { label: "Automations", built: false },
    ],
  },
  { label: "Suivre", items: [{ label: "Suivi", built: false }] },
  { label: "Système", items: [{ label: "Paramètres", built: false }] },
];

interface SidebarProps {
  /** Ouvre (ou remet au premier plan) le panneau `panelId` du cockpit — passé par
   * `Cockpit.tsx`, qui seul possède l'API dockview. */
  onOpenPanel?: (panelId: string, title: string) => void;
}

export function Sidebar({ onOpenPanel }: SidebarProps) {
  return (
    <aside className="flex h-screen w-56 flex-shrink-0 flex-col gap-1 border-r border-hikari-line bg-hikari-bg-2 p-3">
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
            {group.items.map((item) => (
              <button
                key={item.label}
                type="button"
                disabled={!item.built}
                onClick={
                  item.built && item.panelId
                    ? () => onOpenPanel?.(item.panelId as string, item.label)
                    : undefined
                }
                className={`flex w-full items-center gap-2.5 rounded-[7px] px-2.5 py-2.5 text-left text-[13.5px] font-medium transition ${
                  item.built
                    ? "bg-hikari-accent/[.14] text-hikari-accent"
                    : "cursor-not-allowed text-hikari-txt-faint"
                }`}
              >
                <span>{item.label}</span>
                {!item.built && (
                  <span className="ml-auto text-[10px] text-hikari-txt-faint">
                    bientôt
                  </span>
                )}
              </button>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
