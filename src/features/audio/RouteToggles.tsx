// Les deux interrupteurs de destination d'une piste, tels que la maquette les dessine :
// « 🎧 Écoute » et « 📡 Diffusé ».
//
// Ils remplacent une phrase d'état (« Public seul ») doublée d'un réglage caché derrière un
// engrenage. Une phrase se lit, elle ne se manipule pas : pour changer la destination du
// son, il fallait ouvrir une fenêtre (Jay, 2026-09-05 : « pas optimisée ni intuitive »).
//
// La traduction vers le réglage à trois valeurs du moteur vit dans `routing.ts`, éprouvée
// sans écran. Ici il n'y a que le dessin et le geste.

import {
  type AudioRouting,
  toMonitoring,
  toRouting,
  wouldSilenceEverything,
} from "./routing";
import type { AudioMonitoring } from "./types";

interface RouteTogglesProps {
  /** Le nom de la piste — il entre dans le nom accessible de chaque interrupteur. */
  source: string;
  monitoring: AudioMonitoring;
  disabled?: boolean;
  onChange: (monitoring: AudioMonitoring) => void;
}

interface ToggleProps {
  label: string;
  icon: string;
  on: boolean;
  /** Renseigné quand le geste est refusé : dit POURQUOI, jamais un bouton mort sans raison. */
  blocked?: string;
  disabled: boolean;
  onClick: () => void;
}

function Toggle({ label, icon, on, blocked, disabled, onClick }: ToggleProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || Boolean(blocked)}
      aria-pressed={on}
      title={blocked ?? label}
      className={`flex flex-1 items-center justify-center gap-1.5 rounded-[6px] border px-2 py-1 text-[11.5px] font-medium transition
        focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-hikari-accent
        disabled:cursor-not-allowed disabled:opacity-50
        ${
          on
            ? "border-hikari-accent/50 bg-hikari-accent/15 text-hikari-accent"
            : "border-hikari-line text-hikari-txt-faint hover:text-hikari-txt"
        }`}
    >
      <span aria-hidden="true">{icon}</span>
      {label}
    </button>
  );
}

export function RouteToggles({
  source,
  monitoring,
  disabled = false,
  onChange,
}: RouteTogglesProps) {
  const routing = toRouting(monitoring);

  const flip = (key: keyof AudioRouting) => {
    onChange(toMonitoring({ ...routing, [key]: !routing[key] }));
  };

  const blockedReason = (key: keyof AudioRouting) =>
    wouldSilenceEverything(routing, key)
      ? "Dernière destination du son — utilise « Couper » pour rendre la piste muette"
      : undefined;

  return (
    // `<fieldset>` et non un `div` étiqueté : l'élément natif porte le rôle de groupe, et
    // une étiquette posée sur un `div` sans rôle ne s'accroche à rien — un lecteur d'écran
    // annoncerait deux boutons isolés sans dire de quelle piste il s'agit.
    <fieldset
      className="m-0 flex gap-1.5 border-0 p-0"
      aria-label={`Destination du son de ${source}`}
    >
      <Toggle
        label="Écoute"
        icon="🎧"
        on={routing.listen}
        blocked={blockedReason("listen")}
        disabled={disabled}
        onClick={() => flip("listen")}
      />
      <Toggle
        label="Diffusé"
        icon="📡"
        on={routing.broadcast}
        blocked={blockedReason("broadcast")}
        disabled={disabled}
        onClick={() => flip("broadcast")}
      />
    </fieldset>
  );
}
