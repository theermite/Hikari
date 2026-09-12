// Section « Encodage » du panneau Paramètres — résolution/cadence, encodeur, débit.
//
// Née du retour de Jay (2026-09-12) : ~65 % d'images perdues en direct parce que la
// composition se choisissait rien qu'à la taille de l'écran, sans jamais tenir compte de
// sa connexion. "Auto" reste le comportement d'aujourd'hui — rien ne change tant que
// personne n'a choisi autre chose ici.
//
// Sauvegarde immédiate à chaque choix (comme `DeviceSettings.tsx`) : pas de bouton
// "Enregistrer" à oublier. Prend effet au prochain lancement du moteur (l'aperçu
// démarre le moteur — le réglage se lit une fois, au lancement, ADR-013).

import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useState } from "react";
import {
  type CompositionChoice,
  DEFAULT_ENCODING_SETTINGS,
  type EncoderChoice,
  type EncodingSettings,
  loadEncodingSettings,
  saveEncodingSettings,
} from "../../settings/encodingSettings";

const COMPOSITION_CHOICES: { value: CompositionChoice; label: string }[] = [
  { value: "auto", label: "Auto (écran)" },
  { value: "1920x1080@60", label: "1080p 60" },
  { value: "1280x720@60", label: "720p 60" },
  { value: "854x480@30", label: "480p 30" },
];

const ENCODER_CHOICES: { value: EncoderChoice; label: string }[] = [
  { value: "auto", label: "Auto (détecté)" },
  { value: "nvenc", label: "NVENC" },
  { value: "x264", label: "X264" },
];

function ChoiceGroup<T extends string>({
  choices,
  value,
  onChange,
}: {
  choices: { value: T; label: string }[];
  value: T;
  onChange: (next: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {choices.map((choice) => (
        <button
          key={choice.value}
          type="button"
          onClick={() => onChange(choice.value)}
          aria-pressed={value === choice.value}
          className={`rounded-[6px] border px-2 py-1 text-[12px] transition ${
            value === choice.value
              ? "border-hikari-accent text-hikari-accent"
              : "border-hikari-line text-hikari-txt-dim hover:text-hikari-txt"
          }`}
        >
          {choice.label}
        </button>
      ))}
    </div>
  );
}

export function EncodingSettingsPanel(_props: IDockviewPanelProps) {
  const [settings, setSettings] = useState<EncodingSettings>(
    DEFAULT_ENCODING_SETTINGS,
  );
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    loadEncodingSettings().then((saved) => {
      setSettings(saved);
      setLoaded(true);
    });
  }, []);

  const update = (over: Partial<EncodingSettings>) => {
    const next = { ...settings, ...over };
    setSettings(next);
    void saveEncodingSettings(next);
  };

  // Rien à afficher avant la première lecture : montrer "Auto" un instant, puis basculer
  // sur une valeur sauvegardée différente, ferait clignoter l'écran sans raison.
  if (!loaded) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3">
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-[11px] uppercase tracking-wider text-hikari-txt-faint">
          Résolution et cadence
        </legend>
        <ChoiceGroup
          choices={COMPOSITION_CHOICES}
          value={settings.composition}
          onChange={(composition) => update({ composition })}
        />
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-[11px] uppercase tracking-wider text-hikari-txt-faint">
          Encodeur
        </legend>
        <ChoiceGroup
          choices={ENCODER_CHOICES}
          value={settings.encoder}
          onChange={(encoder) => update({ encoder })}
        />
        <p className="text-[11px] text-hikari-txt-faint">
          Ignoré si ta machine ne le détecte pas réellement — jamais forcé à
          l'aveugle.
        </p>
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-[11px] uppercase tracking-wider text-hikari-txt-faint">
          Débit (kbit/s)
        </legend>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => update({ bitrateKbps: "auto" })}
            aria-pressed={settings.bitrateKbps === "auto"}
            className={`rounded-[6px] border px-2 py-1 text-[12px] transition ${
              settings.bitrateKbps === "auto"
                ? "border-hikari-accent text-hikari-accent"
                : "border-hikari-line text-hikari-txt-dim hover:text-hikari-txt"
            }`}
          >
            Auto (calculé)
          </button>
          <input
            type="number"
            min={1}
            placeholder="ex. 4000"
            value={settings.bitrateKbps === "auto" ? "" : settings.bitrateKbps}
            onChange={(event) => {
              const raw = event.target.value;
              update({ bitrateKbps: raw === "" ? "auto" : raw });
            }}
            className="w-24 rounded-[6px] border border-hikari-line bg-hikari-bg-2 px-2 py-1 text-[12px] text-hikari-txt"
            aria-label="Débit manuel en kbit/s"
          />
        </div>
      </fieldset>
    </div>
  );
}
