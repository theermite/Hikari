// Le numéro de version, en haut du cockpit.
//
// Pourquoi : Jay installe UNE fois et reçoit ensuite les mises à jour dans l'app. Sans
// numéro à l'écran, la seule façon de savoir s'il était à jour était de réinstaller — soit
// exactement le geste que la mise à jour dans l'app supprime (Jay, 2026-09-06).
//
// Le numéro vient de la configuration de l'application, figé à la construction : c'est le
// même fichier qui décide de la version installée, donc les deux ne peuvent pas diverger.
// Aucun appel au système, donc rien qui puisse échouer à l'exécution et laisser la case
// vide.

import { useUpdateCheck } from "./useUpdateCheck";

/** Ce que le canal a répondu, dit en mots — et jamais plus que ce qu'il a répondu. */
function channelLabel(
  status: ReturnType<typeof useUpdateCheck>["status"],
  version: string | undefined,
): string {
  if (status === "available") return `· ${version} disponible`;
  if (status === "current") return "· à jour";
  if (status === "unreachable") return "· canal pas joignable";
  return "";
}

export function VersionTag() {
  const { status, update } = useUpdateCheck();
  const label = channelLabel(status, update?.version);

  return (
    <span
      className="ml-auto flex items-center gap-1.5 text-[11px] text-hikari-txt-faint"
      title={
        status === "unreachable"
          ? "Impossible de joindre le canal de mise à jour — l'app fonctionne normalement."
          : undefined
      }
    >
      <span className="tabular-nums">v{__APP_VERSION__}</span>
      {/* Ce numéro est le contrat avec le canal de mise à jour : le bousculer à chaque
      compilation annoncerait des versions jamais publiées. Ce qui manque à l'utilisateur
      n'est pas un autre numéro, c'est de savoir QUELLE construction il regarde — deux
      fenêtres identiques affichaient « v0.4.0 », l'une installée, l'autre compilée à
      l'instant (Jay, 2026-09-06). */}
      {import.meta.env.DEV && (
        <span className="text-hikari-accent">· développement</span>
      )}
      {label && (
        <span
          className={status === "available" ? "text-hikari-accent" : undefined}
        >
          {label}
        </span>
      )}
    </span>
  );
}
