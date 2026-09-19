// Infos de diffusion Twitch (F-054) — thin `invoke` wrapper, aucune logique ici (même
// principe que `chat/api.ts`).

import { invoke } from "@tauri-apps/api/core";
import type {
  CategorySuggestion,
  ChannelInfo,
  ChannelInfoPatch,
} from "./types";

/** Les infos ACTUELLES de la chaîne du compte Twitch connecté. */
export function getStreamInfo(): Promise<ChannelInfo> {
  return invoke("stream_info_get");
}

/** Les catégories Twitch dont le nom correspond à `query`. */
export function searchCategories(query: string): Promise<CategorySuggestion[]> {
  return invoke("stream_info_search_categories", { query });
}

/** Écrit `patch` sur la chaîne du compte connecté — seuls les champs présents changent. */
export function updateStreamInfo(patch: ChannelInfoPatch): Promise<void> {
  return invoke("stream_info_update", { patch });
}
