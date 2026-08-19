/**
 * AudioPanel — le contenu de la fenêtre de réglages d'un périphérique : qui l'entend,
 * anti-bruit.
 *
 * Sorti de AudioPanel.tsx le 2026-08-19 : le fichier faisait 558 lignes, au-dessus du
 * plafond BLOQUANT de 500 (Quality.md). Repris tel quel.
 */

import { VolumeSlider } from "./AudioMeters";
import { setAudioMonitoring, setNoiseSettings } from "./api";
import {
  hasLevel,
  levelToStrength,
  NOISE_METHODS,
  strengthToLevel,
} from "./noiseSettings";
import type { AudioSourceInfo } from "./types";

/** Formulé par QUI entend, jamais par le nom technique du routage. */
const MONITORING_CHOICES: {
  value: AudioSourceInfo["monitoring"];
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

/** Le contenu de la fenêtre de réglages d'un périphérique. */
export function DeviceSettings({
  source,
  busy,
  run,
}: {
  source: AudioSourceInfo;
  busy: boolean;
  run: (action: Promise<void>) => void;
}) {
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

      {/* Le volume du retour n'est PAS ici : il vit sur la ligne du mixeur, à portée
          directe (Jay, 2026-08-05). Cette fenêtre ne garde que ce qu'on règle rarement. */}

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
