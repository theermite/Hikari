// Mirrors `PreflightOutcome` (preflight_bridge.rs) — one real check result, never a
// presumed default (F-003): either an encoder was actually detected, or Go Live is
// blocked with the reason shown (F-012).

export interface PreflightOutcome {
  ok: boolean;
  encoder_name: string | null;
  hardware: boolean | null;
  reason: string | null;
  /** Le débit montant réel mesuré, en kbit/s (B9, 2026-09-12) — `null` seulement quand la
   * mesure elle-même n'a pas pu s'exécuter (voir `reason` dans ce cas). */
  measured_upload_kbps: number | null;
  /** Le meilleur palier que cette mesure et cet encodeur tiennent réellement — même forme
   * que `CompositionChoice` sans le "auto" (`encodingSettings.ts`). `null` seulement quand
   * `measured_upload_kbps` l'est aussi. */
  proposed_composition: { width: number; height: number; fps: number } | null;
  /** Le débit que ce réglage proposé enverrait réellement sur cette machine. */
  proposed_bitrate_kbps: number | null;
}
