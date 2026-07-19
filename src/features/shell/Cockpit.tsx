// Cockpit — la vraie coque à panneaux (B-shell, mono-fenêtre). Remplace l'écran plat de
// B0.3. Détachement 2ᵉ écran et centre de santé (F-106) DIFFÉRÉS : le premier dépend du
// spike B0.4 (non fait), le second dépend de données réelles multi-plateformes (B3, non
// fait) — voir PET fiche B-shell. Ce qui est livré ici : panneaux dock/onglets/redimension,
// sauvegarde/restauration de layout, presets Préparation/Live/Focus.

import type {
  DockviewApi,
  DockviewReadyEvent,
  IDockviewPanelProps,
} from "dockview-react";
import { DockviewReact } from "dockview-react";
import { useCallback, useRef, useState } from "react";
import "dockview-react/dist/styles/dockview.css";
import { DeckPanel } from "../deck/DeckPanel";
import { loadLayout, restoreLayout, saveLayout } from "./layout";
import { AccountsPanel } from "./panels/AccountsPanel";
import { PlaceholderPanel } from "./panels/PlaceholderPanel";
import { PRESETS, type PresetId, resolvePreset } from "./presets";
import { Sidebar } from "./Sidebar";

const PANEL_COMPONENTS: Record<
  string,
  React.FunctionComponent<IDockviewPanelProps>
> = {
  "twitch-connect": AccountsPanel,
  deck: DeckPanel,
  placeholder: PlaceholderPanel,
};

/** Builds the default layout — the two panels wired to real backends today (connexion
 * Twitch, B2b ; deck local, B4) plus a labeled placeholder standing in for the panel
 * not built yet (Aperçu), so the dock/tab/resize behavior has more than two panels to
 * demonstrate. */
function buildDefaultLayout(api: DockviewApi): void {
  const twitch = api.addPanel({
    id: "twitch-connect",
    component: "twitch-connect",
    title: "Comptes",
  });
  const deck = api.addPanel({
    id: "deck",
    component: "deck",
    title: "Deck",
    position: { referencePanel: twitch.id, direction: "right" },
  });
  api.addPanel({
    id: "preview-placeholder",
    component: "placeholder",
    title: "Aperçu (à venir)",
    params: { label: "Câblage complet du moteur, brique à part." },
    position: { referencePanel: deck.id, direction: "below" },
  });
}

export function Cockpit() {
  const apiRef = useRef<DockviewApi | null>(null);
  const [activePreset, setActivePreset] = useState<PresetId>(
    resolvePreset(null),
  );

  const onReady = useCallback((event: DockviewReadyEvent) => {
    apiRef.current = event.api;

    loadLayout()
      .then((saved) => {
        if (saved) {
          restoreLayout(event.api, saved);
        } else {
          buildDefaultLayout(event.api);
        }
      })
      .catch(() => {
        // Coffre indisponible/corrompu — un layout par défaut vaut mieux qu'un cockpit vide.
        buildDefaultLayout(event.api);
      });

    event.api.onDidLayoutChange(() => {
      saveLayout(event.api).catch(() => {
        // La sauvegarde échoue rarement (coffre local) ; ne jamais bloquer l'UI dessus.
      });
    });
  }, []);

  const switchPreset = (id: PresetId) => {
    setActivePreset(id);
    // Les presets ne portent pas encore de disposition propre (aucun 2ᵉ layout construit
    // tant que B-auto/B4/l'aperçu n'existent pas) — la bascule change l'état affiché, la
    // disposition réelle par preset arrive avec les écrans qu'elle doit organiser.
  };

  return (
    <div className="flex h-screen font-hikari bg-hikari-bg text-hikari-txt">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 flex-shrink-0 items-center gap-4 border-b border-hikari-line bg-hikari-bg-2 px-4">
          <h1 className="text-[14px] font-semibold tracking-tight">
            Cockpit Live
          </h1>
          <div className="flex gap-0.5 rounded-full border border-hikari-line bg-hikari-bg-3 p-0.5">
            {PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => switchPreset(preset.id)}
                className={`rounded-full px-3 py-1 text-[12.5px] font-medium transition ${
                  activePreset === preset.id
                    ? "bg-hikari-accent text-[#1a1206]"
                    : "text-hikari-txt-dim hover:text-hikari-txt"
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </header>
        <div className="dockview-theme-dark flex-1 bg-hikari-bg">
          <DockviewReact components={PANEL_COMPONENTS} onReady={onReady} />
        </div>
      </div>
    </div>
  );
}
