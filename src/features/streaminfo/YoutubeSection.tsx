// Volet YouTube du panneau « Infos direct » (F-054) — Jay, 2026-09-19 : « as-tu fait le
// panneau des descriptions pour YouTube aussi ? ». Pas de recherche à la frappe ici :
// YouTube n'a pas de « catégorie de direct » comme Twitch, seulement une taxonomie fixe
// (`videoCategories.list`) posée sur la VIDÉO derrière le direct — un menu déroulant
// suffit, jamais un texte libre pour un choix fermé.

import { useEffect, useRef, useState } from "react";
import { SectionTitle } from "../../components/ui/SectionTitle";
import {
  getYoutubeCategories,
  getYoutubeStreamInfo,
  updateYoutubeStreamInfo,
} from "./api";
import type { CategoryOption, VideoInfoPatch } from "./types";

const TITLE_MAX = 100;
const DESCRIPTION_MAX = 5000;

interface Baseline {
  title: string;
  description: string;
  categoryId: string;
  tags: string[];
}

export function YoutubeSection() {
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [tagDraft, setTagDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const baseline = useRef<Baseline | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Les deux lectures sont indépendantes : la liste des catégories ne dépend pas du
    // direct actif, et un échec sur l'une ne doit pas priver l'écran de l'autre — un menu
    // déroulant vide reste utilisable, un titre pré-rempli aussi.
    getYoutubeCategories()
      .then((options) => {
        if (!cancelled) setCategories(options);
      })
      .catch((error: unknown) => {
        console.error("streaminfo: getYoutubeCategories failed", error);
      });
    getYoutubeStreamInfo()
      .then((info) => {
        if (cancelled) return;
        setTitle(info.title);
        setDescription(info.description);
        setCategoryId(info.category_id);
        setTags(info.tags);
        baseline.current = {
          title: info.title,
          description: info.description,
          categoryId: info.category_id,
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

  const addTag = () => {
    const value = tagDraft.trim();
    if (!value || tags.includes(value)) {
      setTagDraft("");
      return;
    }
    setTags([...tags, value]);
    setTagDraft("");
  };

  const removeTag = (tag: string) => setTags(tags.filter((t) => t !== tag));

  const titleTooLong = title.length > TITLE_MAX;
  const titleEmpty = title.trim().length === 0;
  const descriptionTooLong = description.length > DESCRIPTION_MAX;
  const canPublish =
    !titleTooLong && !titleEmpty && !descriptionTooLong && !saving;

  const publish = () => {
    if (!baseline.current) return;
    const patch: VideoInfoPatch = {};
    if (title !== baseline.current.title) patch.title = title;
    if (description !== baseline.current.description)
      patch.description = description;
    if (categoryId && categoryId !== baseline.current.categoryId)
      patch.category_id = categoryId;
    if (JSON.stringify(tags) !== JSON.stringify(baseline.current.tags))
      patch.tags = tags;
    // Rien de changé : le backend refuserait un patch vide de toute façon
    // (`validate_patch`) — inutile de faire l'aller-retour.
    if (Object.keys(patch).length === 0) return;

    setSaving(true);
    setSaveError(null);
    setSaved(false);
    updateYoutubeStreamInfo(patch)
      .then(() => {
        baseline.current = { title, description, categoryId, tags };
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
      <div className="flex flex-col gap-1.5">
        <SectionTitle>YouTube</SectionTitle>
        <p className="text-[12.5px] leading-relaxed text-hikari-txt-dim">
          {loadError}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <SectionTitle>YouTube</SectionTitle>

      {saveError ? (
        <p role="alert" className="text-[12.5px] text-hikari-red">
          {saveError}
        </p>
      ) : null}

      <fieldset className="flex flex-col gap-1.5">
        <label
          htmlFor="youtube-title"
          className="text-[11px] uppercase tracking-wider text-hikari-txt-faint"
        >
          Titre
        </label>
        <input
          id="youtube-title"
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
          htmlFor="youtube-description"
          className="text-[11px] uppercase tracking-wider text-hikari-txt-faint"
        >
          Description
        </label>
        <textarea
          id="youtube-description"
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className="rounded-[6px] border border-hikari-line bg-hikari-bg-2 px-2 py-1 text-[13px] text-hikari-txt"
        />
        <p
          className={`text-[11px] ${descriptionTooLong ? "text-hikari-red" : "text-hikari-txt-faint"}`}
        >
          {description.length}/{DESCRIPTION_MAX}
        </p>
      </fieldset>

      <fieldset className="flex flex-col gap-1.5">
        <label
          htmlFor="youtube-category"
          className="text-[11px] uppercase tracking-wider text-hikari-txt-faint"
        >
          Catégorie
        </label>
        <select
          id="youtube-category"
          value={categoryId}
          onChange={(event) => setCategoryId(event.target.value)}
          className="rounded-[6px] border border-hikari-line bg-hikari-bg-2 px-2 py-1 text-[13px] text-hikari-txt"
        >
          {categoryId && !categories.some((c) => c.id === categoryId) ? (
            // La catégorie actuelle n'est pas (encore) dans la liste chargée — la montrer
            // quand même plutôt que de faire disparaître le choix déjà fait de Jay.
            <option value={categoryId}>
              Catégorie actuelle ({categoryId})
            </option>
          ) : null}
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
      </fieldset>

      <fieldset className="flex flex-col gap-1.5">
        <label
          htmlFor="youtube-tags"
          className="text-[11px] uppercase tracking-wider text-hikari-txt-faint"
        >
          Tags
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
          id="youtube-tags"
          type="text"
          value={tagDraft}
          onChange={(event) => setTagDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              addTag();
            }
          }}
          placeholder="Ajouter un tag, Entrée pour valider…"
          className="rounded-[6px] border border-hikari-line bg-hikari-bg-2 px-2 py-1 text-[13px] text-hikari-txt"
        />
      </fieldset>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={publish}
          disabled={!canPublish}
          className="rounded-full bg-hikari-accent px-4 py-1.5 text-[13px] font-semibold text-[#1a1206] transition hover:brightness-110 disabled:opacity-50"
        >
          {saving ? "Publication…" : "Publier sur YouTube"}
        </button>
        {saved ? (
          <span className="text-[12px] text-hikari-green">
            Publié sur YouTube.
          </span>
        ) : null}
      </div>
    </div>
  );
}
