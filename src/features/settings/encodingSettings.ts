// Réglages d'encodage (B-settings, onglet Encodage) — persistés via tauri-plugin-store,
// même pattern que `shell/layout.ts`. "auto" partout = comportement d'aujourd'hui
// (composition et débit calculés depuis l'écran et la machine, `encoding.rs`) : un
// utilisateur qui n'a jamais ouvert cet écran ne voit RIEN changer.
//
// `composition` ici règle la résolution/cadence de SORTIE — ce qui est encodé et envoyé
// au stream — jamais le canevas où les sources sont posées (position, taille). Le moteur
// (`engine::main::composition()` contre `output_composition()`) garde les deux séparés
// depuis le 2026-09-12 : les confondre déplaçait chaque source à chaque changement de
// résolution (bug du zoom d'aperçu).
//
// La résolution+cadence de sortie reste UN SEUL choix, jamais deux réglages indépendants
// — les mêmes paliers que le calcul automatique (`encoding.rs`, « peu de paliers, jamais
// une échelle continue »), pour qu'un réglage manuel ne propose jamais une combinaison
// que le moteur n'a jamais fait tourner.
//
// Née du retour de Jay (2026-09-12) : ~65 % d'images perdues en direct, la sortie
// choisie rien qu'à la taille de l'écran ne correspondant ni à sa machine ni à sa
// connexion.

import { load, type Store } from "@tauri-apps/plugin-store";

const STORE_FILE = "encoding-settings.json";
const SETTINGS_KEY = "settings";

export type CompositionChoice =
  | "auto"
  | "1920x1080@60"
  | "1280x720@60"
  | "854x480@30";

export type EncoderChoice = "auto" | "nvenc" | "x264";

export interface EncodingSettings {
  composition: CompositionChoice;
  encoder: EncoderChoice;
  /** "auto", ou le débit choisi en kbit/s — en texte, la même forme que ce que le moteur
   * lit (`overrides.rs` côté Rust) : aucune conversion à double sens à maintenir. */
  bitrateKbps: "auto" | string;
}

export const DEFAULT_ENCODING_SETTINGS: EncodingSettings = {
  composition: "auto",
  encoder: "auto",
  bitrateKbps: "auto",
};

let storePromise: Promise<Store> | null = null;

function getStore(): Promise<Store> {
  storePromise ??= load(STORE_FILE, { autoSave: true });
  return storePromise;
}

/** Charge les réglages sauvegardés, ou les valeurs "auto" par défaut si rien n'a jamais
 * été enregistré (premier lancement, ou store effacé). */
export async function loadEncodingSettings(): Promise<EncodingSettings> {
  const store = await getStore();
  const saved = await store.get<EncodingSettings>(SETTINGS_KEY);
  return saved ?? DEFAULT_ENCODING_SETTINGS;
}

export async function saveEncodingSettings(
  settings: EncodingSettings,
): Promise<void> {
  const store = await getStore();
  await store.set(SETTINGS_KEY, settings);
}
