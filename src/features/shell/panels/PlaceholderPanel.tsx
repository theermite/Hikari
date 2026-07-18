// Panneau vide, honnête sur ce qu'il n'est pas encore — jamais faire semblant qu'une
// fonctionnalité existe (Dignity : l'utilisateur ne doit jamais deviner ce qui est réel).

import type { IDockviewPanelProps } from "dockview-react";

export function PlaceholderPanel(
  props: IDockviewPanelProps<{ label?: string }>,
) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 bg-neutral-900 p-6 text-center text-neutral-500">
      <p className="text-sm">{props.params.label ?? "Pas encore construit."}</p>
    </div>
  );
}
