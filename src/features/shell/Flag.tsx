// Les drapeaux du sélecteur de langue, DESSINÉS et non écrits en émoji.
//
// Windows ne dessine pas les émojis de drapeau : il rend 🇫🇷 comme les deux lettres « FR »,
// et le sélecteur affichait donc « FR FR » (constaté par Jay, 2026-09-05). Aucune police
// installée par défaut n'y change quoi que ce soit — c'est une décision de Microsoft, pas
// un défaut de configuration.
//
// Trois rectangles valent donc mieux qu'un émoji : ils s'affichent partout, à la taille
// qu'on choisit, et ne dépendent d'aucune police.

interface FlagProps {
  /** Le code de la langue. Les trois que le projet vise (Conventions : FR source, EN, ES). */
  lang: "fr" | "en" | "es";
}

/** Bandes verticales — la forme des drapeaux français ; les autres ont leur propre tracé. */
const FLAGS: Record<FlagProps["lang"], React.ReactNode> = {
  fr: (
    <>
      <rect width="7" height="14" fill="#002654" />
      <rect x="7" width="7" height="14" fill="#fff" />
      <rect x="14" width="7" height="14" fill="#ce1126" />
    </>
  ),
  es: (
    <>
      <rect width="21" height="14" fill="#c60b1e" />
      <rect y="3.5" width="21" height="7" fill="#ffc400" />
    </>
  ),
  en: (
    <>
      <rect width="21" height="14" fill="#012169" />
      <path d="M0 0l21 14M21 0L0 14" stroke="#fff" strokeWidth="2.8" />
      <path d="M10.5 0v14M0 7h21" stroke="#fff" strokeWidth="4.6" />
      <path d="M10.5 0v14M0 7h21" stroke="#c8102e" strokeWidth="2.8" />
    </>
  ),
};

export function Flag({ lang }: FlagProps) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 21 14"
      className="h-3.5 w-[21px] shrink-0 rounded-[2px] ring-1 ring-black/40"
    >
      {FLAGS[lang]}
    </svg>
  );
}
