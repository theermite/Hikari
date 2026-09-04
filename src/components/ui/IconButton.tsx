// IconButton — un bouton qui ne montre qu'un pictogramme, mais qui se NOMME.
//
// Ce qu'il corrige : les panneaux affichent aujourd'hui des rangées de ↑ ↓ ✎ ✕ sans
// aucun nom. Au clavier comme au lecteur d'écran, ce sont des boutons identiques et
// muets ; à la souris, ils font moins de 24 px et se ratent. Le nom est donc obligatoire
// (`label`), et la zone cliquable ne descend pas sous 28 px — le pictogramme reste petit,
// la cible ne l'est pas.
//
// `pressed` sert aux bascules (l'œil qui montre ou cache une source) : l'état part dans
// `aria-pressed`, jamais dans la seule couleur.

interface IconButtonProps {
  /** Ce que fait le bouton, en clair. Lu par les lecteurs d'écran, montré au survol. */
  label: string;
  icon: string;
  onClick: () => void;
  /** Renseigné uniquement pour une bascule : l'état marche/arrêt du bouton. */
  pressed?: boolean;
  disabled?: boolean;
  tone?: "default" | "danger";
}

export function IconButton({
  label,
  icon,
  onClick,
  pressed,
  disabled = false,
  tone = "default",
}: IconButtonProps) {
  const toneClass =
    tone === "danger"
      ? "hover:bg-hikari-red/15 hover:text-hikari-red"
      : "hover:bg-hikari-bg-3 hover:text-hikari-txt";
  const pressedClass = pressed ? "bg-hikari-accent/15 text-hikari-accent" : "";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      className={`inline-flex h-7 w-7 items-center justify-center rounded-md text-[13px] text-hikari-txt-dim transition
        focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-hikari-accent
        disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-transparent
        ${pressedClass} ${toneClass}`}
    >
      <span aria-hidden="true">{icon}</span>
    </button>
  );
}
