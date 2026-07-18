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
import { loadLayout, restoreLayout, saveLayout } from "./layout";
import { PlaceholderPanel } from "./panels/PlaceholderPanel";
import { TwitchConnectPanel } from "./panels/TwitchConnectPanel";
import { PRESETS, type PresetId, resolvePreset } from "./presets";

const PANEL_COMPONENTS: Record<
  string,
  React.FunctionComponent<IDockviewPanelProps>
> = {
  "twitch-connect": TwitchConnectPanel,
  placeholder: PlaceholderPanel,
};

/** Builds the default layout — the ONE panel that does something real today (connexion
 * Twitch) plus two labeled placeholders standing in for panels not built yet (Deck,
 * Aperçu), so the dock/tab/resize behavior has more than one panel to demonstrate. */
function buildDefaultLayout(api: DockviewApi): void {
  const twitch = api.addPanel({
    id: "twitch-connect",
    component: "twitch-connect",
    title: "Comptes",
  });
  const deck = api.addPanel({
    id: "deck-placeholder",
    component: "placeholder",
    title: "Deck (à venir)",
    params: { label: "Arrive avec B-auto puis B4." },
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
    <div className="flex h-screen flex-col bg-neutral-950 text-neutral-100">
      <header className="flex items-center gap-2 border-b border-neutral-800 px-4 py-2">
        <h1 className="mr-4 text-lg font-semibold tracking-tight">Hikari 光</h1>
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            onClick={() => switchPreset(preset.id)}
            className={`rounded px-3 py-1 text-sm transition ${
              activePreset === preset.id
                ? "bg-purple-600 text-white"
                : "text-neutral-400 hover:bg-neutral-800"
            }`}
          >
            {preset.label}
          </button>
        ))}
      </header>
      <div className="dockview-theme-dark flex-1">
        <DockviewReact components={PANEL_COMPONENTS} onReady={onReady} />
      </div>
    </div>
  );
}
