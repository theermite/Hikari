// Les réglages d'UNE source texte posée dans une scène (2026-09-07).
//
// Jay : « mettre une source de texte sans réglage, sans personnalisation, je trouve ça très
// inutile ». Le greffon du moteur porte police, taille, couleur, contour et alignement
// depuis toujours ; rien ne les atteignait.
//
// Dépliés SOUS la ligne de la source, comme les réglages de caméra, et pour la même raison :
// l'image du moteur est une fenêtre native qui se dessine au-dessus de tout contenu web,
// donc une fenêtre par-dessus l'obligerait à se retirer. Régler un texte sans le voir n'a
// pas de sens.
//
// Ce qui N'EST PAS ici, volontairement : le dégradé, le mode journal de chat, les dimensions
// forcées. Un panneau qui montre tout ne se règle plus, et ces trois-là ne servent presque
// jamais à un direct. Ils s'ajouteront si le besoin arrive.

import { invoke } from "@tauri-apps/api/core";
import { useEffect, useState } from "react";
import {
  clampFontSize,
  clampOutlineSize,
  type Rgb,
  type TextAlign,
  type TextSettings,
} from "./textSettings";

interface Props {
  scene: string;
  name: string;
  /** Le texte affiché aujourd'hui. Jay, 2026-09-07 : « il faudrait que je puisse éditer le
   * texte » — jusqu'ici il n'était réglable qu'à la création de la source. */
  text: string;
  settings: TextSettings;
  /** Remonte le choix pour qu'il soit RETENU d'une session à l'autre. Sans cela, les
   * réglages s'appliqueraient à l'écran et disparaîtraient au prochain lancement. */
  onChange: (settings: TextSettings) => void;
}

const BUTTON =
  "rounded-[8px] border border-hikari-line px-2.5 py-1 text-[12.5px] transition hover:border-hikari-accent";
const ACTIVE = "border-hikari-accent text-hikari-accent";
const IDLE = "text-hikari-txt-dim hover:text-hikari-txt";
const FIELD =
  "rounded-[8px] border border-hikari-line bg-hikari-bg px-2 py-1 text-[12.5px] text-hikari-txt";

/** Les polices proposées : celles que l'application EMBARQUE, plus les deux valeurs sûres de
 * Windows. Aucune police n'est nommée sans être disponible — c'est la fausse promesse que
 * Jay a attrapée le 2026-09-07 sur le panneau d'adaptation. */
const FACES = [
  "Inter",
  "Atkinson Hyperlegible",
  "OpenDyslexic",
  "Segoe UI",
  "Arial",
  "Georgia",
  "Impact",
];

const ALIGNS: { value: TextAlign; label: string }[] = [
  { value: "left", label: "Gauche" },
  { value: "center", label: "Centre" },
  { value: "right", label: "Droite" },
];

function toHex({ r, g, b }: Rgb): string {
  const part = (n: number) => n.toString(16).padStart(2, "0");
  return `#${part(r)}${part(g)}${part(b)}`;
}

/** Lit une couleur écrite en hexadécimal. Une valeur illisible rend `null` plutôt qu'un noir
 * par défaut : un noir silencieux ferait croire à un choix que personne n'a fait. */
function fromHex(hex: string): Rgb | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const n = Number.parseInt(m[1], 16);
  return { r: (n >> 16) & 0xff, g: (n >> 8) & 0xff, b: n & 0xff };
}

/** Un champ de texte qui ne PART qu'à la validation, jamais à chaque frappe — même raison
 * que `NumberField` : envoyer au moteur à chaque lettre ferait une faute de frappe partir
 * en direct avant même d'être finie. */
function TextField(props: {
  id: string;
  label: string;
  initial: string;
  onCommit: (value: string) => void;
}) {
  const [draft, setDraft] = useState(props.initial);
  useEffect(() => setDraft(props.initial), [props.initial]);

  // Un texte vide est refuse par l'appelant (garde a la creation de la source) — le champ
  // doit alors REVENIR a ce qui est reellement affiche, sinon il mentirait : vide a l'ecran
  // pendant que la scene montre toujours l'ancien texte.
  const commit = () => {
    if (draft.trim() === "") {
      setDraft(props.initial);
      return;
    }
    props.onCommit(draft);
  };

  return (
    <div className="flex items-center gap-2">
      <label className="text-[12.5px] text-hikari-txt-dim" htmlFor={props.id}>
        {props.label}
      </label>
      <input
        id={props.id}
        type="text"
        className={`${FIELD} flex-1`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
        }}
      />
    </div>
  );
}

/** Un champ de nombre qui ne se borne QU'À LA VALIDATION, jamais à chaque frappe.
 *
 * Borner en cours de frappe rend le champ inutilisable : effacer « 48 » pour retaper donne
 * un champ vide, aussitôt ramené au minimum, et les chiffres suivants s'empilent dessus —
 * taper « 96 » produisait 500. Défaut trouvé par son propre test, jamais parti à l'écran.
 *
 * La saisie vit donc en texte libre le temps de la frappe, et la borne s'applique quand
 * l'utilisateur quitte le champ ou valide.
 */
function NumberField(props: {
  id: string;
  label: string;
  value: number;
  width: string;
  clamp: (n: number) => number;
  onCommit: (n: number) => void;
}) {
  const [draft, setDraft] = useState(String(props.value));
  // La valeur peut changer ailleurs (rejeu de session, autre écran) : le brouillon suit.
  useEffect(() => setDraft(String(props.value)), [props.value]);

  const commit = () => {
    const borne = props.clamp(Number(draft));
    setDraft(String(borne));
    if (borne !== props.value) props.onCommit(borne);
  };

  return (
    <>
      <label className="text-[12.5px] text-hikari-txt-dim" htmlFor={props.id}>
        {props.label}
      </label>
      <input
        id={props.id}
        type="number"
        className={`${FIELD} ${props.width}`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
        }}
      />
    </>
  );
}

export function TextControls({ scene, name, text, settings, onChange }: Props) {
  /** Applique ET retient. Les deux ensemble, jamais l'un sans l'autre : appliquer sans
   * retenir perd le réglage au prochain lancement, retenir sans appliquer ment à l'écran. */
  const apply = (next: TextSettings) => {
    onChange(next);
    invoke("set_text_settings", { scene, name, settings: next }).catch(
      (error: unknown) => {
        console.error("text: set_text_settings failed", error);
      },
    );
  };

  const patch = (bout: Partial<TextSettings>) =>
    apply({ ...settings, ...bout });

  /** Envoie le texte édité au moteur — jamais vide, même garde qu'à la création de la
   * source : un texte vide est un rectangle invisible que l'utilisateur chercherait dans
   * sa scène sans jamais le voir. */
  const commitText = (valeur: string) => {
    if (valeur.trim() === "") return;
    if (valeur === text) return;
    invoke("set_text_content", { scene, name, text: valeur }).catch(
      (error: unknown) => {
        console.error("text: set_text_content failed", error);
      },
    );
  };

  return (
    <div className="mt-1 flex flex-col gap-2 rounded-hikari border border-hikari-line bg-hikari-bg-3 px-3 py-2">
      <TextField
        id={`content-${name}`}
        label="Texte"
        initial={text}
        onCommit={commitText}
      />
      <div className="flex flex-wrap items-center gap-2">
        <label
          className="text-[12.5px] text-hikari-txt-dim"
          htmlFor={`face-${name}`}
        >
          Police
        </label>
        <select
          id={`face-${name}`}
          className={FIELD}
          value={settings.face}
          onChange={(e) => patch({ face: e.target.value })}
        >
          {FACES.map((face) => (
            <option key={face} value={face}>
              {face}
            </option>
          ))}
        </select>

        <NumberField
          id={`size-${name}`}
          label="Taille"
          value={settings.size}
          width="w-20"
          clamp={clampFontSize}
          onCommit={(size) => patch({ size })}
        />

        <button
          type="button"
          aria-pressed={settings.bold}
          className={`${BUTTON} ${settings.bold ? ACTIVE : IDLE} font-bold`}
          onClick={() => patch({ bold: !settings.bold })}
        >
          Gras
        </button>
        <button
          type="button"
          aria-pressed={settings.italic}
          className={`${BUTTON} ${settings.italic ? ACTIVE : IDLE} italic`}
          onClick={() => patch({ italic: !settings.italic })}
        >
          Italique
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label
          className="text-[12.5px] text-hikari-txt-dim"
          htmlFor={`color-${name}`}
        >
          Couleur du texte
        </label>
        <input
          id={`color-${name}`}
          type="color"
          className="h-7 w-10 rounded-[6px] border border-hikari-line bg-hikari-bg"
          value={toHex(settings.color)}
          onChange={(e) => {
            const couleur = fromHex(e.target.value);
            if (couleur) patch({ color: couleur });
          }}
        />

        <button
          type="button"
          aria-pressed={settings.outline}
          className={`${BUTTON} ${settings.outline ? ACTIVE : IDLE}`}
          onClick={() => patch({ outline: !settings.outline })}
          title="Un contour rend le texte lisible sur n'importe quel fond"
        >
          Contour
        </button>

        {settings.outline && (
          <>
            <label
              className="text-[12.5px] text-hikari-txt-dim"
              htmlFor={`outline-color-${name}`}
            >
              Couleur du contour
            </label>
            <input
              id={`outline-color-${name}`}
              type="color"
              className="h-7 w-10 rounded-[6px] border border-hikari-line bg-hikari-bg"
              value={toHex(settings.outline_color)}
              onChange={(e) => {
                const couleur = fromHex(e.target.value);
                if (couleur) patch({ outline_color: couleur });
              }}
            />
            <NumberField
              id={`outline-size-${name}`}
              label="Épaisseur"
              value={settings.outline_size}
              width="w-16"
              clamp={clampOutlineSize}
              onCommit={(outline_size) => patch({ outline_size })}
            />
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12.5px] text-hikari-txt-dim">Alignement</span>
        {ALIGNS.map((align) => (
          <button
            key={align.value}
            type="button"
            aria-pressed={settings.align === align.value}
            className={`${BUTTON} ${settings.align === align.value ? ACTIVE : IDLE}`}
            onClick={() => patch({ align: align.value })}
          >
            {align.label}
          </button>
        ))}
      </div>
    </div>
  );
}
