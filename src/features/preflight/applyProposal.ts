// Applique un réglage proposé par le pré-vol — partagé entre `PreflightPanel.tsx` (bouton
// « Appliquer ») et `LiveBar.tsx` (bannière de "Démarrer", Jay 2026-09-13 : laisser le choix
// à l'utilisateur, informé du risque, avec un réglage plus prudent suggéré). Écrit une seule
// fois pour ne jamais diverger entre les deux écrans.

import {
  type CompositionChoice,
  loadEncodingSettings,
  saveEncodingSettings,
} from "../settings/encodingSettings";

/** Le réglage proposé, mis en forme comme `EncodingSettingsPanel.tsx` sait déjà le lire —
 * MÊMES paliers que `preflight.rs` `PALIERS`, jamais une valeur inventée ici. */
export function toCompositionChoice(composition: {
  width: number;
  height: number;
  fps: number;
}): CompositionChoice {
  return `${composition.width}x${composition.height}@${composition.fps}` as CompositionChoice;
}

/** Pose la résolution proposée et remet le débit sur "auto". Un débit choisi à la main
 * PRIME sur la résolution au démarrage du direct (`stream.rs`) — le laisser en place
 * ferait ignorer la proposition qu'on vient d'appliquer (relecture indépendante,
 * 2026-09-12). "auto" retombe sur le calcul fait pour CE palier. */
export async function applyProposedComposition(composition: {
  width: number;
  height: number;
  fps: number;
}): Promise<void> {
  const current = await loadEncodingSettings();
  await saveEncodingSettings({
    ...current,
    composition: toCompositionChoice(composition),
    bitrateKbps: "auto",
  });
}
