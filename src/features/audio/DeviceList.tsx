/**
 * AudioPanel — un petit bouton icône générique, et la liste des appareils pas encore
 * ajoutés au mixeur.
 *
 * Sortis de AudioPanel.tsx le 2026-08-19 : le fichier faisait 558 lignes, au-dessus du
 * plafond BLOQUANT de 500 (Quality.md). Repris tels quels.
 */

// La piece partagee remplace la copie locale : le meme bouton etait defini ici ET dans
// scenes/ScenesControls.tsx. Re-exportee pour que les appelants gardent leur import.
export { IconButton } from "../../components/ui/IconButton";

import type { AudioDevice } from "./types";

/** The devices of one side that are not in the mixer yet, each one click away from being
 * added. An empty list says why it is empty rather than showing nothing at all. */
export function DeviceList({
  title,
  devices,
  emptyLabel,
  busy,
  onAdd,
}: {
  title: string;
  devices: AudioDevice[];
  emptyLabel: string;
  busy: boolean;
  onAdd: (device: AudioDevice) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <h4 className="text-[11px] uppercase tracking-wider text-hikari-txt-faint">
        {title}
      </h4>
      {devices.length === 0 ? (
        <p className="text-[12px] text-hikari-txt-faint">{emptyLabel}</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {devices.map((device) => (
            <li key={device.device_id}>
              <button
                type="button"
                onClick={() => onAdd(device)}
                disabled={busy}
                className="w-full truncate rounded-[6px] border border-hikari-line px-2 py-1 text-left text-[12.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt disabled:opacity-50"
              >
                + {device.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
