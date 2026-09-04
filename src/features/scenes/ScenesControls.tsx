/**
 * ScenesPanel — petits controles partages : pictogrammes de source, et deux boutons
 * generiques (icone + fleche d'empilement).
 *
 * Sortis de ScenesPanel.tsx le 2026-08-19 : le fichier faisait 850 lignes, au-dessus du
 * plafond BLOQUANT de 500 (Quality.md). Repris tels quels.
 */

import type React from "react";

// La piece partagee remplace la copie locale (deux definitions du meme bouton dans le
// projet). Re-exportee ici pour que les appelants gardent leur import.
export { IconButton } from "../../components/ui/IconButton";

export const SOURCE_ICON: Record<string, string> = {
  game_capture: "🎮",
  window_capture: "🪟",
  monitor_capture: "🖥️",
  dshow_input: "🎥",
};

export const KIND_TO_LIBOBS: Record<string, string> = {
  game: "game_capture",
  window: "window_capture",
  monitor: "monitor_capture",
};

/** Une flèche d'empilement, plus discrète que les boutons de scène pour ne pas confondre
 * « ordre des scènes » et « ordre des sources DANS une scène ». */
export function OrderButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="px-1 text-hikari-txt-faint transition hover:text-hikari-accent disabled:cursor-not-allowed disabled:opacity-30"
    >
      {children}
    </button>
  );
}
