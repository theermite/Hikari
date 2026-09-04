// Panneau Audio — le mixeur (B6) : ajouter un micro ou le son du bureau, régler son volume,
// le couper, voir son niveau, et ouvrir ses réglages fins.
//
// Le son ne dépend PAS de la scène : le moteur place les sources audio sur leurs propres
// canaux, donc le son survit à un changement de scène — comme le mixeur global d'OBS.
//
// Partage visuel décidé avec les experts UX et accessibilité (2026-08-05) : la LIGNE ne porte
// que l'essentiel permanent (niveau, couper, volume) plus une phrase d'état en lecture seule ;
// tout le réglage fin part dans une fenêtre dédiée. Empiler quatre rangées de boutons par
// périphérique rendait la colonne illisible dès deux sources.

import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Modal } from "../../components/Modal";
import { Panel } from "../../components/ui/Panel";
import { LevelBar, VolumeSlider } from "./AudioMeters";
import {
  addAudioSource,
  listAudioDevices,
  removeAudioSource,
  setAudioMuted,
  setAudioVolume,
  setMonitorVolume,
} from "./api";
import { DeviceList, IconButton } from "./DeviceList";
import { DeviceSettings } from "./DeviceSettings";
import { METER_DANGER_DB } from "./meter";
import { statusLine } from "./noiseSettings";
import type {
  AudioDevice,
  AudioEngineMessage,
  AudioSourceInfo,
  AudioSourceKind,
} from "./types";

const KIND_LABEL: Record<AudioSourceKind, string> = {
  input: "Micro",
  output: "Son du bureau",
};

/** Délai minimal entre deux annonces de saturation. Une alerte vocale répétée à chaque image
 * interromprait tout ce que le lecteur d'écran est en train de dire. */
const CLIPPING_ALERT_INTERVAL_MS = 3000;

/** Demande la liste au moteur, en avalant le seul échec qui n'en est pas un : « le moteur
 * n'est pas encore démarré ». Au lancement c'est l'état normal ; le panneau le dit déjà en
 * toutes lettres, et une erreur rouge reprocherait à l'utilisateur son ordre d'ouverture. */
function askForDevices(): void {
  listAudioDevices().catch(() => undefined);
}

export function AudioPanel(_props: IDockviewPanelProps) {
  const [inputs, setInputs] = useState<AudioDevice[] | null>(null);
  const [outputs, setOutputs] = useState<AudioDevice[] | null>(null);
  const [sources, setSources] = useState<AudioSourceInfo[]>([]);
  const [levels, setLevels] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [settingsFor, setSettingsFor] = useState<string | null>(null);
  const [clipping, setClipping] = useState<string | null>(null);
  const lastClippingAt = useRef(0);

  useEffect(() => {
    const unlisten = listen<AudioEngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      // Le moteur vient de démarrer : c'est le seul moment où il PEUT répondre. Le panneau
      // s'affiche bien avant lui (le moteur démarre à l'ouverture de l'Aperçu).
      if (msg.type === "ready") askForDevices();
      if (msg.type === "audio_devices") {
        setInputs(msg.inputs ?? []);
        setOutputs(msg.outputs ?? []);
        setError(null);
      }
      if (msg.type === "audio_sources" && msg.items) setSources(msg.items);
      if (msg.type === "audio_levels" && msg.levels) {
        setLevels(
          Object.fromEntries(msg.levels.map((l) => [l.name, l.magnitude_db])),
        );
        const hot = msg.levels.find((l) => l.magnitude_db >= METER_DANGER_DB);
        const now = Date.now();
        if (hot && now - lastClippingAt.current > CLIPPING_ALERT_INTERVAL_MS) {
          lastClippingAt.current = now;
          setClipping(hot.name);
        }
      }
      if (msg.type === "error" && msg.message) setError(msg.message);
    });
    return () => {
      unlisten.then((f) => f());
    };
  }, []);

  useEffect(() => {
    askForDevices();
  }, []);

  const run = useCallback((action: Promise<void>) => {
    setError(null);
    setBusy(true);
    action
      .catch((err: unknown) => setError(String(err)))
      .finally(() => setBusy(false));
  }, []);

  const notYetAdded = (devices: AudioDevice[] | null) =>
    (devices ?? []).filter(
      (device) => !sources.some((source) => source.name === device.name),
    );

  const openSettings = sources.find((s) => s.name === settingsFor) ?? null;

  return (
    <Panel title="Audio" badge="écoute / diffusion">
      {inputs === null && (
        <p className="text-hikari-txt-faint">
          Ouvre le panneau Aperçu pour gérer le son.
        </p>
      )}

      {/* Annonce rare et brève, jamais le flux continu du niveau. */}
      {clipping && (
        <p role="alert" className="sr-only">
          Le son sature sur {clipping}
        </p>
      )}

      {sources.length > 0 && (
        <ul className="flex flex-col gap-2">
          {sources.map((source) => {
            const db = levels[source.name] ?? Number.NEGATIVE_INFINITY;
            return (
              <li
                key={source.name}
                className="flex flex-col gap-1.5 rounded-[8px] border border-hikari-line px-3 py-2"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate font-medium">{source.name}</span>
                  <span className="shrink-0 text-[11px] text-hikari-txt-faint">
                    {KIND_LABEL[source.kind]}
                  </span>
                </div>

                <LevelBar name={source.name} db={db} />

                <p className="text-[11px] text-hikari-txt-faint">
                  {statusLine(source)}
                </p>

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

                  <VolumeSlider
                    label={`Volume de ${source.name} pour le public`}
                    value={source.volume_percent}
                    disabled={busy}
                    onChange={(percent) =>
                      run(setAudioVolume(source.name, percent))
                    }
                  />

                  <IconButton
                    label={`Réglages de ${source.name}`}
                    disabled={busy}
                    onClick={() => setSettingsFor(source.name)}
                  >
                    ⚙
                  </IconButton>
                  <IconButton
                    label={`Retirer ${source.name} du mixeur`}
                    disabled={busy}
                    onClick={() => run(removeAudioSource(source.name))}
                  >
                    ✕
                  </IconButton>
                </div>

                {/* Le volume du retour vit sur la LIGNE et non dans les réglages (Jay,
                    2026-08-05) : régler son propre retour est un geste fréquent, pas un
                    réglage rare — l'enfouir derrière ⚙ ajoutait des clics à chaque fois.
                    Il n'apparaît que sur les sources que le streamer écoute, donc les
                    autres gardent une ligne courte. */}
                {source.monitoring !== "none" && (
                  <div className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      title="Volume dans ton casque"
                      className="shrink-0 text-[11.5px] text-hikari-txt-faint"
                    >
                      🎧
                    </span>
                    <VolumeSlider
                      label={`Volume de ${source.name} dans mon casque`}
                      value={source.monitor_volume_percent}
                      disabled={busy}
                      onChange={(percent) =>
                        run(setMonitorVolume(source.name, percent))
                      }
                    />
                  </div>
                )}
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
            onAdd={(device) =>
              run(addAudioSource(device.device_id, "input", device.name))
            }
          />
          <DeviceList
            title="Sons du bureau"
            devices={notYetAdded(outputs)}
            emptyLabel="Toutes tes sorties sont déjà dans le mixeur."
            busy={busy}
            onAdd={(device) =>
              run(addAudioSource(device.device_id, "output", device.name))
            }
          />
        </div>
      )}

      {error && <p className="text-hikari-red">❌ {error}</p>}

      <Modal
        open={openSettings !== null}
        title={openSettings ? `Réglages — ${openSettings.name}` : ""}
        onClose={() => setSettingsFor(null)}
      >
        {openSettings && (
          <DeviceSettings source={openSettings} busy={busy} run={run} />
        )}
      </Modal>
    </Panel>
  );
}
