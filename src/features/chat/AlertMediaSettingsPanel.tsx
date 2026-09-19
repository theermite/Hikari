// Réglage « Alertes → médias » (F-033/F-034) — un média par type d'alerte Twitch, posé
// EN PERMANENCE dans la médiathèque (`OVERLAY_SCENE_NAME`), jamais recréé puis détruit à
// chaque alerte (Jay, 2026-09-15 : « il faut que la source reste », pour un redéclenchement
// futur par deck). Le nom de la source DANS la médiathèque est le type d'alerte lui-même —
// une seule médiathèque, une source par type, jamais de collision à gérer.
//
// Deux boutons de famille (Image/Vidéo) au lieu du grand sélecteur `AddSourceModal` :
// une alerte n'a que deux familles pertinentes (jamais un jeu, une fenêtre ou un écran),
// le montrer réduirait la carte à ce qui compte.

import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useState } from "react";
import {
  addCaptureSource,
  removeSource,
  requestSceneList,
  setSourceVisible,
  showMediaFor,
} from "../scenes/api";
import { FILE_FILTERS, parseTimedMediaSeconds } from "../scenes/sourcePicker";
import type { EngineMessage } from "../scenes/types";
import { OVERLAY_SCENE_NAME } from "../scenes/types";
import { requestScreen } from "../shell/panelActions";
import { ALERT_KIND_LABEL, ALERT_KINDS } from "./alerts";
import type { ChatSettings } from "./chatSettings";
import { loadChatSettings, patchChatSettings } from "./chatSettings";
import type { AlertMediaRule, ChatAlert } from "./types";

type Kind = ChatAlert["kind"];

const DEFAULT_SECONDS = "3";

function AlertMediaRow({
  kind,
  rule,
  posed,
  onChange,
  onRemove,
}: {
  kind: Kind;
  rule: AlertMediaRule | undefined;
  /** Vrai si la médiathèque porte RÉELLEMENT une source sous ce nom en ce moment —
   * jamais deviné depuis le réglage : les deux peuvent diverger après un essai
   * interrompu (vécu 2026-09-15, un réglage périmé pointait sur une source disparue). */
  posed: boolean;
  onChange: (next: AlertMediaRule) => void;
  onRemove: () => void;
}) {
  const [seconds, setSeconds] = useState(
    rule ? String(rule.durationMs / 1000) : DEFAULT_SECONDS,
  );

  // La ligne suit le réglage RÉEL (un autre écran a pu le changer) tant que l'utilisateur
  // n'est pas en train d'y taper.
  useEffect(() => {
    setSeconds(rule ? String(rule.durationMs / 1000) : DEFAULT_SECONDS);
  }, [rule]);

  // Pose (ou remplace) la source de médiathèque pour CE type d'alerte — toujours nommée
  // d'après le type, cachée par défaut : seule une alerte, ou plus tard un deck, la montre.
  const pick = (fileKind: "image" | "video") => {
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
      // Retirer AVANT de reposer seulement s'il y a RÉELLEMENT quelque chose à
      // remplacer — sinon le moteur le refuse (rien à retirer) et le dit dans un
      // bandeau visible à l'écran (vécu 2026-09-15, un réglage périmé le déclenchait
      // même au tout premier réglage).
      const clear = posed
        ? removeSource(OVERLAY_SCENE_NAME, kind)
        : Promise.resolve();
      clear
        .then(() => addCaptureSource(OVERLAY_SCENE_NAME, fileKind, path, kind))
        .then(() => setSourceVisible(OVERLAY_SCENE_NAME, kind, false))
        .then(() => {
          const durationMs = parseTimedMediaSeconds(seconds) ?? 3_000;
          onChange({ durationMs });
        });
    });
  };

  const commitSeconds = (value: string) => {
    setSeconds(value);
    if (!rule) return; // Rien à corriger tant qu'aucun média n'est posé.
    const durationMs = parseTimedMediaSeconds(value);
    if (durationMs === null) return;
    onChange({ durationMs });
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-[6px] border border-hikari-line px-2 py-1.5">
      <span className="w-32 shrink-0 text-[12.5px] text-hikari-txt">
        {ALERT_KIND_LABEL[kind]}
      </span>

      <input
        type="number"
        min="0"
        step="0.5"
        value={seconds}
        onChange={(event) => commitSeconds(event.target.value)}
        aria-label={`Durée en secondes pour l'alerte ${ALERT_KIND_LABEL[kind]}`}
        className="w-16 rounded-[6px] border border-hikari-line bg-hikari-bg px-2 py-1 text-[12px] text-hikari-txt"
      />
      <span className="text-[11px] text-hikari-txt-faint">s</span>

      {posed && rule ? (
        <>
          <span className="min-w-0 flex-1 truncate text-[11.5px] text-hikari-txt-dim">
            média posé dans la médiathèque
          </span>
          <button
            type="button"
            onClick={() => {
              const durationMs =
                parseTimedMediaSeconds(seconds) ?? rule.durationMs;
              showMediaFor(OVERLAY_SCENE_NAME, kind, durationMs).catch(
                (error: unknown) =>
                  console.error("alertMedia: test failed", error),
              );
              // Paramètres n'a pas d'Aperçu — ramener sur le cockpit pour que le résultat
              // se voie tout de suite (Jay, 2026-09-15 : « je ne vois pas l'aperçu »).
              requestScreen("cockpit");
            }}
            title="Voir ce média s'afficher maintenant, comme le ferait l'alerte"
            className="rounded-[6px] border border-hikari-accent px-2 py-1 text-[11.5px] text-hikari-accent transition hover:brightness-110"
          >
            Tester
          </button>
          <button
            type="button"
            onClick={() => pick("image")}
            className="rounded-[6px] border border-hikari-line px-2 py-1 text-[11.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
          >
            Changer…
          </button>
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
  /** Ce que la médiathèque porte RÉELLEMENT en ce moment — jamais déduit du réglage,
   * les deux peuvent diverger (vécu 2026-09-15). Alimenté par le même flux que le
   * panneau Scènes, jamais une copie qui pourrait dater. */
  const [posedNames, setPosedNames] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadChatSettings().then(setSettings);
  }, []);

  useEffect(() => {
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type !== "scene_list" || !msg.scenes) return;
      const overlay = msg.scenes.find(
        (scene) => scene.name === OVERLAY_SCENE_NAME,
      );
      setPosedNames(
        new Set(overlay?.sources.map((source) => source.name) ?? []),
      );
    });
    // Le moteur ne renvoie `scene_list` que sur un vrai changement — cet écran, ouvert
    // après le dernier, attendrait sinon indéfiniment (même défaut déjà fermé ailleurs,
    // `useEngineSessionSync.ts`).
    requestSceneList().catch(() => {});
    return () => {
      unlisten.then((f) => f());
    };
  }, []);

  if (!settings) return null;

  const apply = (nextAlertMedia: ChatSettings["alertMedia"]) => {
    patchChatSettings({ alertMedia: nextAlertMedia }).then(setSettings);
  };

  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-[11px] text-hikari-txt-faint">
        Le média reste posé — une alerte le montre puis le cache, sans jamais le
        détruire. Vide = rien ne s'affiche pour ce type. Position et taille se
        règlent dans le panneau Scènes, sur la scène « 🖼️ médiathèque ».
      </p>
      {ALERT_KINDS.map((kind) => (
        <AlertMediaRow
          key={kind}
          kind={kind}
          rule={settings.alertMedia[kind]}
          posed={posedNames.has(kind)}
          onChange={(rule) => apply({ ...settings.alertMedia, [kind]: rule })}
          onRemove={() => {
            removeSource(OVERLAY_SCENE_NAME, kind).catch(() => {});
            const { [kind]: _removed, ...rest } = settings.alertMedia;
            apply(rest);
          }}
        />
      ))}
    </div>
  );
}
