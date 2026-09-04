// Segmented — la bascule à deux ou trois positions de la maquette : Préparation / Live,
// Écoute / Diffusé. Un seul choix actif à la fois.
//
// Pourquoi un groupe nommé : sans le nom du réglage, un lecteur d'écran annonce deux
// boutons isolés et jamais « Disposition : Live ». L'utilisateur entend le choix sans
// savoir de quoi il s'agit. Le nom voyage donc dans `aria-label` du groupe, et l'état
// actif dans `aria-pressed` — jamais dans la seule couleur du fond.

export interface SegmentedOption<T extends string> {
  id: T;
  label: string;
}

interface SegmentedProps<T extends string> {
  /** Le réglage dont il s'agit, en clair (« Disposition », « Sortie audio »). */
  label: string;
  options: SegmentedOption<T>[];
  value: T;
  onChange: (id: T) => void;
}

export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: SegmentedProps<T>) {
  return (
    // `<fieldset>` plutôt que `role="group"` : l'élément natif porte déjà le rôle, et un
    // rôle déclaré à la main se désynchronise du balisage à la première refonte.
    <fieldset
      aria-label={label}
      className="m-0 inline-flex gap-0.5 rounded-full border border-hikari-line bg-hikari-bg-3 p-0.5"
    >
      {options.map((option) => {
        const active = option.id === value;
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.id)}
            className={`rounded-full px-3 py-1 text-[12.5px] font-medium transition
              focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-hikari-accent
              ${
                active
                  ? "bg-hikari-accent text-[#1a1206]"
                  : "text-hikari-txt-dim hover:text-hikari-txt"
              }`}
          >
            {option.label}
          </button>
        );
      })}
    </fieldset>
  );
}
