// Badge — la petite pastille de la maquette (« 1 clic », « écoute / diffusion »,
// « EN DIRECT »). Elle qualifie ce que fait un panneau, ou dans quel état il se trouve.
//
// Écrit ici, jamais importé : `@shinkofa/ui` en publie un, mais Hikari est libre et
// public et ne peut pas dépendre d'un paquet propriétaire sur un registre privé
// (`.claude/rules/Lego-Hikari.md`).
//
// Règle tenue : l'information est dans le MOT, la couleur ne fait que l'appuyer. Un état
// porté par la seule couleur disparaît pour qui ne la distingue pas, et n'existe pas du
// tout pour un lecteur d'écran (WCAG 2.2 AA).

import type { ReactNode } from "react";

type Tone = "neutral" | "accent" | "live" | "ok";

const TONES: Record<Tone, string> = {
  neutral: "border-hikari-line bg-hikari-bg-3 text-hikari-txt-dim",
  accent: "border-hikari-accent/30 bg-hikari-accent/15 text-hikari-accent",
  live: "border-hikari-live/40 bg-hikari-live/15 text-hikari-live",
  ok: "border-hikari-green/30 bg-hikari-green/15 text-hikari-green",
};

interface BadgeProps {
  children: ReactNode;
  tone?: Tone;
}

export function Badge({ children, tone = "neutral" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium leading-none ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}
