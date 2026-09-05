// Les pictogrammes de la barre latérale, tracés à l'image de la maquette.
//
// Des traits monochromes, jamais des émojis : la maquette dessine des icônes fines qui
// prennent la couleur du texte à côté d'elles. Un émoji est coloré et figé — il jurerait
// avec l'entrée active en ambre, et resterait vif sur une entrée grisée « bientôt ».
//
// Écrits ici plutôt qu'apportés par une bibliothèque : neuf tracés valent moins qu'une
// dépendance de plus dans une application libre que d'autres devront compiler.

interface IconProps {
  /** Décoratif : le nom de l'entrée est déjà porté par le texte à côté. */
  className?: string;
}

function Svg({
  children,
  className,
}: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-[18px] w-[18px] shrink-0 ${className ?? ""}`}
    >
      {children}
    </svg>
  );
}

export const NAV_ICONS = {
  home: (p: IconProps) => (
    <Svg {...p}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h14V9.5" />
    </Svg>
  ),
  prevol: (p: IconProps) => (
    <Svg {...p}>
      <path d="M12 3a9 9 0 1 0 9 9" />
      <path d="M12 7v5l3 2" />
      <path d="M16.5 3.5 21 8" />
    </Svg>
  ),
  cockpit: (p: IconProps) => (
    <Svg {...p}>
      <path d="M4 6h16M4 12h10M4 18h13" />
      <circle cx="18" cy="12" r="2" />
      <circle cx="9" cy="18" r="2" />
    </Svg>
  ),
  edition: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="6" cy="7" r="2.5" />
      <circle cx="6" cy="17" r="2.5" />
      <path d="M8 8.5 20 17M8 15.5 20 7" />
    </Svg>
  ),
  publication: (p: IconProps) => (
    <Svg {...p}>
      <path d="M5 15c0-5 4-10 10-11 1 5-1 10-6 12l-4-1Z" />
      <path d="M7 17c-1 1-1 3-1 3s2 0 3-1" />
    </Svg>
  ),
  deck: (p: IconProps) => (
    <Svg {...p}>
      <rect x="6" y="2.5" width="12" height="19" rx="2.5" />
      <path d="M11 18.5h2" />
    </Svg>
  ),
  automations: (p: IconProps) => (
    <Svg {...p}>
      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />
    </Svg>
  ),
  suivi: (p: IconProps) => (
    <Svg {...p}>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </Svg>
  ),
  parametres: (p: IconProps) => (
    <Svg {...p}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1" />
    </Svg>
  ),
} as const;

export type NavIconName = keyof typeof NAV_ICONS;
