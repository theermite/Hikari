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
import { AudioPanel } from "../audio/AudioPanel";
import { CameraPanel } from "../camera/CameraPanel";
import { DeckPanel } from "../deck/DeckPanel";
import { PreflightPanel } from "../preflight/PreflightPanel";
import { PreviewPanel } from "../preview/PreviewPanel";
import { ScenesPanel } from "../scenes/ScenesPanel";
import { loadLayout, restoreLayout, saveLayout } from "./layout";
import { AccountsPanel } from "./panels/AccountsPanel";
import { PlaceholderPanel } from "./panels/PlaceholderPanel";
import { SettingsPanel } from "./panels/SettingsPanel";
import { PRESETS, type PresetId, resolvePreset } from "./presets";
import { Sidebar } from "./Sidebar";

const PANEL_COMPONENTS: Record<
  string,
  React.FunctionComponent<IDockviewPanelProps>
> = {
  // Gardé pour désérialiser une disposition sauvegardée avant la migration Comptes →
  // Paramètres (2026-07-24) ; le panneau "twitch-connect" lui-même n'est plus ajouté (voir
  // la migration dans `onReady`, qui le retire au premier chargement).
  "twitch-connect": AccountsPanel,
  settings: SettingsPanel,
  deck: DeckPanel,
  placeholder: PlaceholderPanel,
  preflight: PreflightPanel,
  camera: CameraPanel,
  preview: PreviewPanel,
  scenes: ScenesPanel,
  audio: AudioPanel,
};

/** Adds panel `id` if a (fresh or restored) layout doesn't already have it — a saved
 * layout predates every panel added after it was first written to disk, so this is how a
 * new default panel (e.g. Caméra) reaches an existing install without a manual reset. */
function ensurePanel(
  api: DockviewApi,
  id: string,
  title: string,
  position?: Parameters<DockviewApi["addPanel"]>[0]["position"],
): void {
  if (api.getPanel(id)) return;
  api.addPanel({ id, component: id, title, position });
}

/** Builds the default layout — Caméra occupe la place de gauche (Jay, 2026-07-24 : les
 * comptes ne sont plus dans le cockpit live, seulement dans Paramètres, ouvert depuis la
 * barre latérale). */
function buildDefaultLayout(api: DockviewApi): void {
  const camera = api.addPanel({
    id: "camera",
    component: "camera",
    title: "Caméra",
  });
  const deck = api.addPanel({
    id: "deck",
    component: "deck",
    title: "Deck",
    position: { referencePanel: camera.id, direction: "right" },
  });
  api.addPanel({
    id: "preview",
    component: "preview",
    title: "Aperçu",
    position: { referencePanel: deck.id, direction: "below" },
  });
  api.addPanel({
    id: "preflight",
    component: "preflight",
    title: "Pré-vol",
    position: { referencePanel: camera.id, direction: "below" },
  });
  api.addPanel({
    id: "scenes",
    component: "scenes",
    title: "Scènes",
    position: { referencePanel: camera.id, direction: "below" },
  });
  api.addPanel({
    id: "audio",
    component: "audio",
    title: "Audio",
    position: { referencePanel: camera.id, direction: "below" },
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
          // Un layout sauvegardé avant l'ajout de ce panneau ne l'a jamais vu — rattrapage
          // pour qu'il apparaisse sans que Jay doive réinitialiser sa disposition.
          ensurePanel(event.api, "camera", "Caméra");
          // Le placeholder "Aperçu (à venir)" est remplacé par le vrai panneau — retiré
          // s'il vient d'une disposition sauvegardée avant cette brique.
          const oldPlaceholder = event.api.getPanel("preview-placeholder");
          if (oldPlaceholder) {
            event.api.removePanel(oldPlaceholder);
          }
          ensurePanel(event.api, "preview", "Aperçu");
          // Un layout sauvegardé avant cette brique (multi-scène) ne l'a jamais vu — même
          // rattrapage que les autres panneaux ajoutés après coup.
          ensurePanel(event.api, "scenes", "Scènes", {
            referencePanel: "camera",
            direction: "below",
          });
          // Idem pour le mixeur (B6) : ajouté après coup, absent des dispositions déjà
          // écrites sur le disque.
          ensurePanel(event.api, "audio", "Audio", {
            referencePanel: "camera",
            direction: "below",
          });
          // Migration Comptes → Paramètres (Jay, 2026-07-24) : une disposition sauvegardée
          // avant ce jour a "Comptes" à gauche — la Caméra prend sa place exacte (même
          // groupe d'onglets), et le panneau Comptes du cockpit live disparaît (il reste
          // accessible depuis Paramètres, barre latérale).
          const twitchPanel = event.api.getPanel("twitch-connect");
          if (twitchPanel) {
            const cameraPanel = event.api.getPanel("camera");
            if (cameraPanel && cameraPanel.group !== twitchPanel.group) {
              cameraPanel.api.moveTo({ group: twitchPanel.group });
            }
            event.api.removePanel(twitchPanel);
          }
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

  // Ouvre (ou remet au premier plan) un panneau par son id — utilisé par la sidebar pour
  // les entrées "built". Un layout déjà sauvegardé avant l'ajout d'un panneau (ex. Pré-vol)
  // ne l'aurait jamais vu ; cette fonction le crée à la demande au lieu de rester invisible.
  const openPanel = useCallback((panelId: string, title: string) => {
    const api = apiRef.current;
    if (!api) return;
    const existing = api.getPanel(panelId);
    if (existing) {
      existing.api.setActive();
      return;
    }
    api.addPanel({ id: panelId, component: panelId, title });
  }, []);

  return (
    <div className="flex h-screen font-hikari bg-hikari-bg text-hikari-txt">
      <Sidebar onOpenPanel={openPanel} />
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
