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
import {
  addAudioSource,
  listAudioDevices,
  removeAudioSource,
  setAudioMonitoring,
  setAudioMuted,
  setAudioVolume,
  setMonitorVolume,
  setNoiseSettings,
} from "./api";
import {
  formatLevel,
  METER_DANGER_DB,
  meterFraction,
  meterZone,
} from "./meter";
import {
  hasLevel,
  levelToStrength,
  NOISE_METHODS,
  statusLine,
  strengthToLevel,
} from "./noiseSettings";
import type {
  AudioDevice,
  AudioEngineMessage,
  AudioMonitoring,
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

/** Formulé par QUI entend, jamais par le nom technique du routage. */
const MONITORING_CHOICES: {
  value: AudioMonitoring;
  label: string;
  hint: string;
}[] = [
  {
    value: "none",
    label: "Public seul",
    hint: "Tes spectateurs l'entendent, toi non.",
  },
  { value: "monitor_only", label: "Moi seul", hint: "Tu l'entends, eux non." },
  {
    value: "monitor_and_output",
    label: "Les deux",
    hint: "Tu l'entends et tes spectateurs aussi, chacun son volume.",
  },
];

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
    <div className="flex h-full flex-col items-stretch justify-start gap-5 overflow-y-auto bg-hikari-bg-3 p-6 text-hikari-txt">
      <h3 className="text-[12px] uppercase tracking-wider text-hikari-txt-faint">
        Audio
      </h3>

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
                    label={`Volume de ${source.name}`}
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
    </div>
  );
}

/** Le niveau : une barre pour l'œil, et une valeur consultable au clavier pour qui n'y voit
 * pas. Séparer les deux est le seul moyen de tenir les deux besoins — la barre change 20 fois
 * par seconde, l'annoncer en continu rendrait le panneau inutilisable, mais la masquer
 * entièrement priverait un utilisateur non-voyant de toute information de niveau. */
function LevelBar({ name, db }: { name: string; db: number }) {
  const fraction = meterFraction(db);
  return (
    <>
      <div
        aria-hidden="true"
        className="h-1.5 w-full overflow-hidden rounded-full bg-hikari-bg"
      >
        <div
          className={`h-full transition-[width] duration-75 motion-reduce:transition-none ${ZONE_COLOR[meterZone(db)]}`}
          style={{ width: `${fraction * 100}%` }}
        />
      </div>
      {/* Consultable à la demande (tabulation), jamais annoncé tout seul : aucune zone
          « live », donc aucune interruption. */}
      {/* Pas de `tabIndex` : un indicateur n'est pas une commande, l'ajouter au parcours de
          tabulation créerait un arrêt sans action pour les utilisateurs clavier voyants. Un
          lecteur d'écran l'atteint par sa propre navigation par éléments, sans tabulation —
          l'information reste donc disponible à la demande, sans jamais être annoncée seule. */}
      <meter
        aria-label={`Niveau de ${name}`}
        min={0}
        max={100}
        value={Math.round(fraction * 100)}
        aria-valuetext={formatLevel(db)}
        className="sr-only"
      />
    </>
  );
}

/** Curseur de volume : nom accessible explicite (plusieurs sources coexistent), unité lue,
 * pas au clavier laissé au navigateur. */
function VolumeSlider({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  disabled?: boolean;
  onChange: (percent: number) => void;
}) {
  return (
    <>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        aria-label={label}
        aria-valuetext={`${value} pour cent`}
        className="flex-1 accent-hikari-accent"
      />
      <span
        aria-hidden="true"
        className="w-9 shrink-0 text-right text-[11.5px] text-hikari-txt-faint"
      >
        {value}%
      </span>
    </>
  );
}

/** Le contenu de la fenêtre de réglages d'un périphérique. */
function DeviceSettings({
  source,
  busy,
  run,
}: {
  source: AudioSourceInfo;
  busy: boolean;
  run: (action: Promise<void>) => void;
}) {
  const hearsMe = source.monitoring !== "none";
  const pushNoise = (
    over: Partial<{ enabled: boolean; method: string; levelDb: number }>,
  ) =>
    run(
      setNoiseSettings(
        source.name,
        over.enabled ?? source.noise_suppression,
        (over.method as AudioSourceInfo["noise_method"]) ?? source.noise_method,
        over.levelDb ?? source.noise_level_db,
      ),
    );

  return (
    <>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-[11px] uppercase tracking-wider text-hikari-txt-faint">
          Qui l'entend
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {MONITORING_CHOICES.map((choice) => (
            <button
              key={choice.value}
              type="button"
              data-autofocus={
                choice.value === source.monitoring ? "" : undefined
              }
              onClick={() => run(setAudioMonitoring(source.name, choice.value))}
              disabled={busy}
              title={choice.hint}
              aria-pressed={source.monitoring === choice.value}
              className={`rounded-[6px] border px-2 py-1 text-[12px] transition disabled:opacity-50 ${
                source.monitoring === choice.value
                  ? "border-hikari-accent text-hikari-accent"
                  : "border-hikari-line text-hikari-txt-dim hover:border-hikari-accent hover:text-hikari-txt"
              }`}
            >
              {choice.label}
            </button>
          ))}
        </div>
      </fieldset>

      {/* Absent, pas grisé, quand personne ne t'écoute : un champ sans effet n'a rien à
          faire à l'écran, et un champ grisé sans explication laisse deviner pourquoi. */}
      {/* Un titre visuel, pas un <label> : le curseur porte déjà son propre nom accessible,
          et l'envelopper le nommerait une seconde fois. */}
      {hearsMe && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[11px] uppercase tracking-wider text-hikari-txt-faint">
            Volume dans mon casque
          </span>
          <span className="flex items-center gap-2">
            <VolumeSlider
              label={`Volume de ${source.name} dans mon casque`}
              value={source.monitor_volume_percent}
              disabled={busy}
              onChange={(percent) =>
                run(setMonitorVolume(source.name, percent))
              }
            />
          </span>
        </div>
      )}

      {source.kind === "input" && (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-[11px] uppercase tracking-wider text-hikari-txt-faint">
            Anti-bruit
          </legend>
          <button
            type="button"
            onClick={() => pushNoise({ enabled: !source.noise_suppression })}
            disabled={busy}
            aria-pressed={source.noise_suppression}
            title="Retire le bruit de fond de la pièce (ventilateur, clavier, rue)."
            className={`self-start rounded-[6px] border px-2 py-1 text-[12px] transition disabled:opacity-50 ${
              source.noise_suppression
                ? "border-hikari-accent text-hikari-accent"
                : "border-hikari-line text-hikari-txt-dim hover:border-hikari-accent hover:text-hikari-txt"
            }`}
          >
            {source.noise_suppression ? "Activé" : "Désactivé"}
          </button>

          {source.noise_suppression && (
            <>
              <div className="flex gap-1.5">
                {NOISE_METHODS.map((method) => (
                  <button
                    key={method.value}
                    type="button"
                    onClick={() => pushNoise({ method: method.value })}
                    disabled={busy}
                    title={method.hint}
                    aria-pressed={source.noise_method === method.value}
                    className={`rounded-[6px] border px-2 py-1 text-[12px] transition disabled:opacity-50 ${
                      source.noise_method === method.value
                        ? "border-hikari-accent text-hikari-accent"
                        : "border-hikari-line text-hikari-txt-dim hover:border-hikari-accent hover:text-hikari-txt"
                    }`}
                  >
                    {method.label}
                  </button>
                ))}
              </div>

              {/* Le moteur n'expose aucun réglage sur la méthode forte : afficher un
                  curseur inerte serait inventer un réglage. */}
              {hasLevel(source.noise_method) && (
                <div className="flex items-center gap-2 text-[12px]">
                  Force
                  <VolumeSlider
                    label={`Force de l'anti-bruit sur ${source.name}`}
                    value={levelToStrength(source.noise_level_db)}
                    disabled={busy}
                    onChange={(strength) =>
                      pushNoise({ levelDb: strengthToLevel(strength) })
                    }
                  />
                </div>
              )}
            </>
          )}
        </fieldset>
      )}
    </>
  );
}

/** A small square control. `label` is the accessible name (WCAG 2.2 AA: the glyph alone says
 * nothing to a screen reader), also shown as the tooltip. */
function IconButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="h-6 w-6 shrink-0 rounded-[6px] border border-hikari-line text-[12px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt disabled:cursor-not-allowed disabled:opacity-30"
    >
      {children}
    </button>
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
