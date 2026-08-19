/**
 * ScenesPanel — petits controles partages : pictogrammes de source, et deux boutons
 * generiques (icone + fleche d'empilement).
 *
 * Sortis de ScenesPanel.tsx le 2026-08-19 : le fichier faisait 850 lignes, au-dessus du
 * plafond BLOQUANT de 500 (Quality.md). Repris tels quels.
 */

import type React from "react";

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

/** A small square control. `label` is the accessible name (WCAG 2.2 AA: the glyph alone
 * says nothing to a screen reader), also shown as the tooltip. */
export function IconButton({
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
      className="h-6 w-6 rounded-[6px] border border-hikari-line text-[12px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt disabled:cursor-not-allowed disabled:opacity-30"
    >
      {children}
    </button>
  );
}
