// Panneau « Infos direct » (F-054) — changer titre, catégorie et tags Twitch sans
// quitter Hikari, plutôt que par le site Twitch dans un onglet à part (Jay, 2026-09-19).
//
// Twitch seulement pour l'instant : YouTube n'a ni le même scope ni la même API pour ce
// geste (`accounts::twitch.rs`, `required_scopes`) — dessiné et marqué « à venir »
// (`ComingSoon`), jamais un bouton qui prétendrait le faire (Dignity).

import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useRef, useState } from "react";
import { ComingSoon } from "../../components/ui/ComingSoon";
import { Panel } from "../../components/ui/Panel";
import { getStreamInfo, searchCategories, updateStreamInfo } from "./api";
import { debounce } from "./debounce";
import type { CategorySuggestion, ChannelInfoPatch } from "./types";

const TITLE_MAX = 140;
const TAGS_MAX = 10;
const TAG_MAX = 25;

/** Ce que `publish` compare pour ne transmettre que ce qui a réellement changé — un
 * champ inchangé ne doit pas voyager, `validate_patch` (backend) refuse d'ailleurs un
 * patch entièrement vide. */
interface Baseline {
  title: string;
  gameId: string;
  tags: string[];
}

export function StreamInfoPanel(_props: IDockviewPanelProps) {
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [gameId, setGameId] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagDraft, setTagDraft] = useState("");
  const [categoryQuery, setCategoryQuery] = useState("");
  const [suggestions, setSuggestions] = useState<CategorySuggestion[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const baseline = useRef<Baseline | null>(null);

  useEffect(() => {
    let cancelled = false;
    getStreamInfo()
      .then((info) => {
        if (cancelled) return;
        setTitle(info.title);
        setGameId(info.game_id);
        setCategoryQuery(info.game_name);
        setTags(info.tags);
        baseline.current = {
          title: info.title,
          gameId: info.game_id,
          tags: info.tags,
        };
        setLoaded(true);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setLoadError(String(error));
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Une seule instance sur toute la vie du panneau : recréée à chaque rendu, `debounce`
  // perdrait son minuteur en cours et chaque frappe relancerait un nouveau délai complet.
  const runSearch = useRef(
    debounce((query: string) => {
      if (!query.trim()) {
        setSuggestions([]);
        return;
      }
      searchCategories(query)
        .then(setSuggestions)
        .catch((error: unknown) => {
          console.error("streaminfo: searchCategories failed", error);
        });
    }, 300),
  ).current;

  const onCategoryInput = (value: string) => {
    setCategoryQuery(value);
    runSearch(value);
  };

  const pickCategory = (suggestion: CategorySuggestion) => {
    setGameId(suggestion.id);
    setCategoryQuery(suggestion.name);
    setSuggestions([]);
  };

  const addTag = () => {
    const value = tagDraft.trim();
    if (!value || tags.length >= TAGS_MAX || tags.includes(value)) {
      setTagDraft("");
      return;
    }
    setTags([...tags, value]);
    setTagDraft("");
  };

  const removeTag = (tag: string) => setTags(tags.filter((t) => t !== tag));

  const titleTooLong = title.length > TITLE_MAX;
  const titleEmpty = title.trim().length === 0;
  const canPublish = !titleTooLong && !titleEmpty && !saving;

  const publish = () => {
    if (!baseline.current) return;
    const patch: ChannelInfoPatch = {};
    if (title !== baseline.current.title) patch.title = title;
    if (gameId && gameId !== baseline.current.gameId) patch.game_id = gameId;
    if (JSON.stringify(tags) !== JSON.stringify(baseline.current.tags))
      patch.tags = tags;
    // Rien de changé : ne pas appeler le backend pour un patch vide qu'il refuserait de
    // toute façon (`validate_patch`) — inutile de faire un aller-retour réseau pour ça.
    if (Object.keys(patch).length === 0) return;

    setSaving(true);
    setSaveError(null);
    setSaved(false);
    updateStreamInfo(patch)
      .then(() => {
        baseline.current = { title, gameId, tags };
        setSaved(true);
        setSaving(false);
      })
      .catch((error: unknown) => {
        setSaveError(String(error));
        setSaving(false);
      });
  };

  if (!loaded) return null;

  if (loadError) {
    return (
      <Panel title="Infos direct">
        <p className="text-[12.5px] leading-relaxed text-hikari-txt-dim">
          {loadError}
        </p>
      </Panel>
    );
  }

  return (
    <Panel title="Infos direct">
      <div className="flex flex-col gap-3">
        {saveError ? (
          <p role="alert" className="text-[12.5px] text-hikari-red">
            {saveError}
          </p>
        ) : null}

        <fieldset className="flex flex-col gap-1.5">
          <label
            htmlFor="streaminfo-title"
            className="text-[11px] uppercase tracking-wider text-hikari-txt-faint"
          >
            Titre
          </label>
          <input
            id="streaminfo-title"
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="rounded-[6px] border border-hikari-line bg-hikari-bg-2 px-2 py-1 text-[13px] text-hikari-txt"
          />
          <p
            className={`text-[11px] ${titleTooLong ? "text-hikari-red" : "text-hikari-txt-faint"}`}
          >
            {title.length}/{TITLE_MAX}
            {titleEmpty ? " — le titre ne peut pas être vide" : ""}
          </p>
        </fieldset>

        <fieldset className="flex flex-col gap-1.5">
          <label
            htmlFor="streaminfo-category"
            className="text-[11px] uppercase tracking-wider text-hikari-txt-faint"
          >
            Catégorie
          </label>
          <input
            id="streaminfo-category"
            type="text"
            value={categoryQuery}
            onChange={(event) => onCategoryInput(event.target.value)}
            placeholder="Rechercher un jeu ou une catégorie…"
            className="rounded-[6px] border border-hikari-line bg-hikari-bg-2 px-2 py-1 text-[13px] text-hikari-txt"
          />
          {suggestions.length > 0 ? (
            <ul className="flex flex-col gap-0.5 rounded-[6px] border border-hikari-line bg-hikari-bg-2 p-1">
              {suggestions.map((suggestion) => (
                <li key={suggestion.id}>
                  <button
                    type="button"
                    onClick={() => pickCategory(suggestion)}
                    className="w-full rounded px-2 py-1 text-left text-[12.5px] text-hikari-txt hover:bg-hikari-bg"
                  >
                    {suggestion.name}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </fieldset>

        <fieldset className="flex flex-col gap-1.5">
          <label
            htmlFor="streaminfo-tags"
            className="text-[11px] uppercase tracking-wider text-hikari-txt-faint"
          >
            Tags ({tags.length}/{TAGS_MAX})
          </label>
          {tags.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="flex items-center gap-1 rounded-full border border-hikari-line px-2 py-0.5 text-[11.5px] text-hikari-txt-dim"
                >
                  {tag}
                  <button
                    type="button"
                    onClick={() => removeTag(tag)}
                    aria-label={`Retirer le tag ${tag}`}
                    className="text-hikari-txt-faint hover:text-hikari-red"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          ) : null}
          <input
            id="streaminfo-tags"
            type="text"
            value={tagDraft}
            onChange={(event) =>
              setTagDraft(event.target.value.slice(0, TAG_MAX))
            }
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === ",") {
                event.preventDefault();
                addTag();
              }
            }}
            placeholder={
              tags.length >= TAGS_MAX
                ? "Maximum atteint"
                : "Ajouter un tag, Entrée pour valider…"
            }
            disabled={tags.length >= TAGS_MAX}
            className="rounded-[6px] border border-hikari-line bg-hikari-bg-2 px-2 py-1 text-[13px] text-hikari-txt disabled:opacity-50"
          />
        </fieldset>

        <ComingSoon what="changer aussi les infos YouTube depuis cet écran">
          <span className="text-[11px] text-hikari-txt-faint">YouTube</span>
        </ComingSoon>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={publish}
            disabled={!canPublish}
            className="rounded-full bg-hikari-accent px-4 py-1.5 text-[13px] font-semibold text-[#1a1206] transition hover:brightness-110 disabled:opacity-50"
          >
            {saving ? "Publication…" : "Publier"}
          </button>
          {saved ? (
            <span className="text-[12px] text-hikari-green">
              Publié sur Twitch.
            </span>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}
