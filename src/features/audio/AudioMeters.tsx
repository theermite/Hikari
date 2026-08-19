/**
 * AudioPanel — le niveau (barre + valeur accessible) et le curseur de volume.
 *
 * Sortis de AudioPanel.tsx le 2026-08-19 : le fichier faisait 558 lignes, au-dessus
 * du plafond BLOQUANT de 500 (Quality.md). Deux petits controles sans etat propre,
 * repris tels quels, reutilises par le panneau et par la fenetre de reglages.
 */

import { formatLevel, meterFraction, meterZone } from "./meter";

const ZONE_COLOR = {
  quiet: "bg-hikari-accent/50",
  good: "bg-hikari-accent",
  danger: "bg-hikari-red",
} as const;

/** Le niveau : une barre pour l'œil, et une valeur consultable au clavier pour qui n'y voit
 * pas. Séparer les deux est le seul moyen de tenir les deux besoins — la barre change 20 fois
 * par seconde, l'annoncer en continu rendrait le panneau inutilisable, mais la masquer
 * entièrement priverait un utilisateur non-voyant de toute information de niveau. */
export function LevelBar({ name, db }: { name: string; db: number }) {
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
export function VolumeSlider({
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
