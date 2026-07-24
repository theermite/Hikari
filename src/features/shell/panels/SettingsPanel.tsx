// Panneau "Paramètres" — accueille les réglages qui n'ont pas besoin d'être en
// permanence sous les yeux pendant un live (Jay, 2026-07-24 : la caméra prend la place de
// gauche, les comptes passent ici). Aucune nouvelle logique : reprend `AccountsPanel` telle
// quelle, seulement déplacée.

import type { IDockviewPanelProps } from "dockview-react";
import { AccountsPanel } from "./AccountsPanel";

export function SettingsPanel(props: IDockviewPanelProps) {
  return (
    <div className="flex h-full flex-col bg-hikari-bg-3 text-hikari-txt">
      <div className="border-b border-hikari-line px-6 py-4">
        <h2 className="text-[14px] font-semibold">Paramètres</h2>
      </div>
      <div className="flex-1 overflow-auto">
        <div className="px-6 py-4">
          <h3 className="mb-2 text-[12px] uppercase tracking-wider text-hikari-txt-faint">
            Comptes
          </h3>
        </div>
        <AccountsPanel {...props} />
      </div>
    </div>
  );
}
