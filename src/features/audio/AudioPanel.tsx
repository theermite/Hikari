// Panneau Audio — le mixeur (B6, tranche 1) : ajouter un micro ou le son du bureau, régler
// son volume, le couper, et voir son niveau bouger en direct.
//
// Le son ne dépend PAS de la scène : le moteur place les sources audio sur leurs propres
// canaux, donc le son survit à un changement de scène — comme le mixeur global d'OBS.

import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useCallback, useEffect, useState } from "react";
import {
  addAudioSource,
  listAudioDevices,
  removeAudioSource,
  setAudioMuted,
  setAudioVolume,
} from "./api";
import { formatLevel, meterFraction, meterZone } from "./meter";
import type {
  AudioDevice,
  AudioEngineMessage,
  AudioSourceInfo,
  AudioSourceKind,
} from "./types";

const ZONE_COLOR = {
  quiet: "bg-hikari-accent/50",
  good: "bg-hikari-accent",
  danger: "bg-hikari-red",
} as const;

const KIND_LABEL: Record<AudioSourceKind, string> = {
  input: "Micro",
  output: "Son du bureau",
};

export function AudioPanel(_props: IDockviewPanelProps) {
  const [inputs, setInputs] = useState<AudioDevice[] | null>(null);
  const [outputs, setOutputs] = useState<AudioDevice[] | null>(null);
  const [sources, setSources] = useState<AudioSourceInfo[]>([]);
  const [levels, setLevels] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const unlisten = listen<AudioEngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "audio_devices") {
        setInputs(msg.inputs ?? []);
        setOutputs(msg.outputs ?? []);
      }
      if (msg.type === "audio_sources" && msg.items) setSources(msg.items);
      if (msg.type === "audio_levels" && msg.levels) {
        setLevels(
          Object.fromEntries(msg.levels.map((l) => [l.name, l.magnitude_db])),
        );
      }
      if (msg.type === "error" && msg.message) setError(msg.message);
    });
    return () => {
      unlisten.then((f) => f());
    };
  }, []);

  // Le moteur ne connaît les périphériques qu'une fois démarré : on redemande à chaque
  // montage du panneau plutôt que de garder une liste qui peut dater d'avant un branchement.
  useEffect(() => {
    listAudioDevices().catch((err: unknown) => setError(String(err)));
  }, []);

  const run = useCallback((action: Promise<void>) => {
    setError(null);
    setBusy(true);
    action
      .catch((err: unknown) => setError(String(err)))
      .finally(() => setBusy(false));
  }, []);

  const add = (device: AudioDevice, kind: AudioSourceKind) => {
    // Le nom affiché du périphérique sert d'identifiant dans le mixeur : c'est ce que
    // l'utilisateur reconnaît, et le moteur refuse un doublon.
    run(addAudioSource(device.device_id, kind, device.name));
  };

  const notYetAdded = (devices: AudioDevice[] | null) =>
    (devices ?? []).filter(
      (device) => !sources.some((source) => source.name === device.name),
    );

  return (
    <div className="flex h-full flex-col items-stretch justify-start gap-5 overflow-y-auto bg-hikari-bg-3 p-6 text-hikari-txt">
      <h3 className="text-[12px] uppercase tracking-wider text-hikari-txt-faint">
        Audio
      </h3>

      {inputs === null && (
        <p className="text-hikari-txt-faint">
          Ouvre le panneau Aperçu pour gérer le son.
        </p>
      )}

      {sources.length > 0 && (
        <ul className="flex flex-col gap-3">
          {sources.map((source) => {
            const db = levels[source.name] ?? Number.NEGATIVE_INFINITY;
            const zone = meterZone(db);
            return (
              <li
                key={source.name}
                className="flex flex-col gap-2 rounded-[8px] border border-hikari-line px-3 py-2"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate font-medium">{source.name}</span>
                  <span className="shrink-0 text-[11px] text-hikari-txt-faint">
                    {KIND_LABEL[source.kind]} · {formatLevel(db)}
                  </span>
                </div>

                {/* Barre décorative, masquée aux lecteurs d'écran : elle change 20 fois par
                    seconde, l'annoncer rendrait le panneau inutilisable. Le niveau est déjà
                    lisible en toutes lettres juste au-dessus (`formatLevel`). */}
                <div
                  aria-hidden="true"
                  className="h-1.5 w-full overflow-hidden rounded-full bg-hikari-bg"
                >
                  <div
                    className={`h-full transition-[width] duration-75 ${ZONE_COLOR[zone]}`}
                    style={{ width: `${meterFraction(db) * 100}%` }}
                  />
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      run(setAudioMuted(source.name, !source.muted))
                    }
                    disabled={busy}
                    aria-pressed={source.muted}
                    className={`shrink-0 rounded-[6px] border px-2 py-0.5 text-[11.5px] transition disabled:opacity-50 ${
                      source.muted
                        ? "border-hikari-red text-hikari-red"
                        : "border-hikari-line text-hikari-txt-dim hover:border-hikari-accent hover:text-hikari-txt"
                    }`}
                  >
                    {source.muted ? "Coupé" : "Couper"}
                  </button>

                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={source.volume_percent}
                    onChange={(event) =>
                      run(
                        setAudioVolume(source.name, Number(event.target.value)),
                      )
                    }
                    aria-label={`Volume de ${source.name}`}
                    className="flex-1 accent-hikari-accent"
                  />
                  <span className="w-9 shrink-0 text-right text-[11.5px] text-hikari-txt-faint">
                    {source.volume_percent}%
                  </span>

                  <button
                    type="button"
                    onClick={() => run(removeAudioSource(source.name))}
                    disabled={busy}
                    aria-label={`Retirer ${source.name} du mixeur`}
                    title={`Retirer ${source.name} du mixeur`}
                    className="h-6 w-6 shrink-0 rounded-[6px] border border-hikari-line text-[12px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt disabled:opacity-50"
                  >
                    ✕
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {inputs !== null && (
        <div className="flex flex-col gap-3">
          <DeviceList
            title="Micros"
            devices={notYetAdded(inputs)}
            emptyLabel="Tous tes micros sont déjà dans le mixeur."
            busy={busy}
            onAdd={(device) => add(device, "input")}
          />
          <DeviceList
            title="Sons du bureau"
            devices={notYetAdded(outputs)}
            emptyLabel="Toutes tes sorties sont déjà dans le mixeur."
            busy={busy}
            onAdd={(device) => add(device, "output")}
          />
        </div>
      )}

      {error && <p className="text-hikari-red">❌ {error}</p>}
    </div>
  );
}

/** The devices of one side that are not in the mixer yet, each one click away from being
 * added. An empty list says why it is empty rather than showing nothing at all. */
function DeviceList({
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
