// L'en-tête d'une carte du cockpit — le titre et sa pastille, sur UNE ligne.
//
// Ce que ça corrige : la pastille (« 1 clic », « écoute / diffusion », « à venir ») vivait
// sous l'onglet, seule sur une deuxième ligne. Trois cartes, trois lignes perdues, et un
// rythme cassé par rapport à la maquette qui pose le titre et sa pastille côte à côte
// (Jay, 2026-09-05 : « tu pourrais les mettre sur une seule ligne »).
//
// La pastille est déclarée ICI, par identifiant de panneau, et non passée par chaque écran :
// elle qualifie la carte, pas son contenu, et c'est l'onglet qui porte le nom.

import type { IDockviewPanelHeaderProps } from "dockview-react";
import type { ReactNode } from "react";
import { Badge } from "../../components/ui/Badge";
import { ComingSoonTag } from "../../components/ui/ComingSoon";
import { IconButton } from "../../components/ui/IconButton";
import { requestAdd } from "./panelActions";

/** Ce que le « + » d'une carte ajoute, en clair. Absent = pas de « + ». */
const ADD_LABELS: Record<string, string> = {
  scenes: "Ajouter une scène",
  audio: "Ajouter une piste au mixeur",
};

/** Ce que chaque carte annonce à côté de son nom. Absente = pas de pastille. */
const PANEL_BADGES: Record<string, ReactNode> = {
  scenes: <Badge>1 clic</Badge>,
  audio: <Badge>écoute / diffusion</Badge>,
  chat: <ComingSoonTag />,
};

export function PanelTab({ api }: IDockviewPanelHeaderProps) {
  const addLabel = ADD_LABELS[api.id];
  return (
    <div className="flex items-center gap-2 px-2.5 py-1">
      <span className="text-[12.5px] font-semibold text-hikari-txt">
        {api.title}
      </span>
      {PANEL_BADGES[api.id]}
      {addLabel ? (
        <IconButton
          label={addLabel}
          onClick={() => {
            // L'onglet ne peut pas ouvrir la fenêtre lui-même : il est dessiné hors de
            // l'arbre du panneau. Il DEMANDE, le panneau décide.
            api.setActive();
            requestAdd(api.id);
          }}
        >
          +
        </IconButton>
      ) : null}
    </div>
  );
}
