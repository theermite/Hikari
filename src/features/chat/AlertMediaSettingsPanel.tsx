// Réglage « Alertes → médias » (F-033/F-034) — un média pop-up par type d'alerte
// Twitch, réutilisant EXACTEMENT la capacité déjà posée côté Scènes (`AddTimedMedia`).
//
// Deux boutons de famille (Image/Vidéo) au lieu du grand sélecteur `AddSourceModal` :
// une alerte n'a que deux familles pertinentes (jamais un jeu, une fenêtre ou un écran),
// le montrer réduirait la carte à ce qui compte.

import { open } from "@tauri-apps/plugin-dialog";
import { useEffect, useState } from "react";
import type { IDockviewPanelProps } from "dockview-react";
import { FILE_FILTERS, nameFromPath, parseTimedMediaSeconds } from "../scenes/sourcePicker";
import { ALERT_KIND_LABEL, ALERT_KINDS } from "./alerts";
import { loadChatSettings, patchChatSettings } from "./chatSettings";
import type { ChatSettings } from "./chatSettings";
import type { AlertMediaRule, ChatAlert } from "./types";

type Kind = ChatAlert["kind"];

const DEFAULT_SCENE = "main";
const DEFAULT_SECONDS = "3";

interface Draft {
  scene: string;
  seconds: string;
}

function draftFor(rule: AlertMediaRule | undefined): Draft {
  return rule
    ? { scene: rule.scene, seconds: String(rule.durationMs / 1000) }
    : { scene: DEFAULT_SCENE, seconds: DEFAULT_SECONDS };
}

function AlertMediaRow({
  kind,
  rule,
  onChange,
  onRemove,
}: {
  kind: Kind;
  rule: AlertMediaRule | undefined;
  onChange: (next: AlertMediaRule) => void;
  onRemove: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => draftFor(rule));

  // La ligne suit le réglage RÉEL (un autre écran a pu le changer) tant que l'utilisateur
  // n'est pas en train d'y taper — sans ça, chaque frappe serait effacée par le réglage
  // encore identique venu du store.
  useEffect(() => {
    setDraft(draftFor(rule));
  }, [rule]);

  const pick = (fileKind: AlertMediaRule["kind"]) => {
    open({
      multiple: false,
      filters: [
        {
          name: fileKind === "image" ? "Images" : "Vidéos",
          extensions: FILE_FILTERS[fileKind] ?? [],
        },
      ],
    }).then((path) => {
      if (typeof path !== "string") return;
      const durationMs = parseTimedMediaSeconds(draft.seconds) ?? 3_000;
      onChange({
        scene: draft.scene.trim() || DEFAULT_SCENE,
        kind: fileKind,
        path,
        durationMs,
      });
    });
  };

  const commitField = (over: Partial<Draft>) => {
    const next = { ...draft, ...over };
    setDraft(next);
    if (!rule) return; // Rien à corriger tant qu'aucun fichier n'est choisi.
    const durationMs = parseTimedMediaSeconds(next.seconds);
    if (durationMs === null || !next.scene.trim()) return;
    onChange({ ...rule, scene: next.scene.trim(), durationMs });
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-[6px] border border-hikari-line px-2 py-1.5">
      <span className="w-32 shrink-0 text-[12.5px] text-hikari-txt">
        {ALERT_KIND_LABEL[kind]}
      </span>

      <input
        type="text"
        value={draft.scene}
        onChange={(event) => commitField({ scene: event.target.value })}
        placeholder="scène"
        aria-label={`Scène pour l'alerte ${ALERT_KIND_LABEL[kind]}`}
        className="w-24 rounded-[6px] border border-hikari-line bg-hikari-bg px-2 py-1 text-[12px] text-hikari-txt placeholder:text-hikari-txt-faint"
      />
      <input
        type="number"
        min="0"
        step="0.5"
        value={draft.seconds}
        onChange={(event) => commitField({ seconds: event.target.value })}
        aria-label={`Durée en secondes pour l'alerte ${ALERT_KIND_LABEL[kind]}`}
        className="w-16 rounded-[6px] border border-hikari-line bg-hikari-bg px-2 py-1 text-[12px] text-hikari-txt"
      />
      <span className="text-[11px] text-hikari-txt-faint">s</span>

      {rule ? (
        <>
          <span className="min-w-0 flex-1 truncate text-[11.5px] text-hikari-txt-dim">
            {nameFromPath(rule.path)}
          </span>
          <button
            type="button"
            onClick={onRemove}
            title="Retirer ce média"
            className="text-hikari-txt-faint transition hover:text-hikari-red"
          >
            ✕
          </button>
        </>
      ) : (
        <>
          <button
            type="button"
            onClick={() => pick("image")}
            className="rounded-[6px] border border-hikari-line px-2 py-1 text-[11.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
          >
            Image…
          </button>
          <button
            type="button"
            onClick={() => pick("video")}
            className="rounded-[6px] border border-hikari-line px-2 py-1 text-[11.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
          >
            Vidéo…
          </button>
        </>
      )}
    </div>
  );
}

export function AlertMediaSettingsPanel(_props: IDockviewPanelProps) {
  const [settings, setSettings] = useState<ChatSettings | null>(null);

  useEffect(() => {
    loadChatSettings().then(setSettings);
  }, []);

  if (!settings) return null;

  const apply = (nextAlertMedia: ChatSettings["alertMedia"]) => {
    patchChatSettings({ alertMedia: nextAlertMedia }).then(setSettings);
  };

  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-[11px] text-hikari-txt-faint">
        Un média qui apparaît puis disparaît tout seul quand l'alerte arrive. Vide = rien
        ne s'affiche pour ce type.
      </p>
      {ALERT_KINDS.map((kind) => (
        <AlertMediaRow
          key={kind}
          kind={kind}
          rule={settings.alertMedia[kind]}
          onChange={(rule) => apply({ ...settings.alertMedia, [kind]: rule })}
          onRemove={() => {
            const { [kind]: _removed, ...rest } = settings.alertMedia;
            apply(rest);
          }}
        />
      ))}
    </div>
  );
}
