// Panneau « Paramètres » — accueille les réglages qui n'ont pas besoin d'être en
// permanence sous les yeux pendant un live (Jay, 2026-07-24 : la caméra prend la place de
// gauche, les comptes passent ici).
//
// C'est LUI qui porte la carte, pas `AccountsPanel` : deux cartes imbriquées afficheraient
// deux en-têtes et deux barres de défilement, l'une dans l'autre.

import type { IDockviewPanelProps } from "dockview-react";
import { Panel } from "../../../components/ui/Panel";
import { SectionTitle } from "../../../components/ui/SectionTitle";
import { AccountsPanel } from "./AccountsPanel";

export function SettingsPanel(props: IDockviewPanelProps) {
  return (
    <Panel title="Paramètres">
      <div className="flex flex-col gap-3">
        <SectionTitle>Comptes</SectionTitle>
        <AccountsPanel {...props} />
      </div>
    </Panel>
  );
}
