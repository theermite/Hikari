// IconButton — un bouton qui ne montre qu'un pictogramme, mais qui se NOMME.
//
// Ce qu'il remplace : DEUX copies du même bouton, dans `audio/DeviceList.tsx` et
// `scenes/ScenesControls.tsx`. Toutes deux nommaient déjà correctement leur bouton
// (`aria-label` + `title`) — ce n'est pas l'accessibilité qui manquait, c'est le
// partage : deux bordures, deux survols, deux panneaux qui ne se ressemblent pas.
//
// Ce que cette version ajoute aux deux copies :
//   - la cible cliquable passe de 24 à 28 px. 24 px se rate à la souris ;
//   - `pressed` pour les bascules (l'œil qui montre ou cache une source) : l'état part
//     dans `aria-pressed`, jamais dans la seule couleur ;
//   - un contour de focus visible au clavier.

import type { ReactNode } from "react";

interface IconButtonProps {
  /** Ce que fait le bouton, en clair. Lu par les lecteurs d'écran, montré au survol. */
  label: string;
  /** Le pictogramme. Passé en enfant pour coller aux appels existants du projet. */
  children: ReactNode;
  onClick: () => void;
  /** Renseigné uniquement pour une bascule : l'état marche/arrêt du bouton. */
  pressed?: boolean;
  disabled?: boolean;
  tone?: "default" | "danger";
}

export function IconButton({
  label,
  children,
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
      <span aria-hidden="true">{children}</span>
    </button>
  );
}
