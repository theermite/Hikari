// Infos de diffusion Twitch (F-054) — thin `invoke` wrapper, aucune logique ici (même
// principe que `chat/api.ts`).

import { invoke } from "@tauri-apps/api/core";
import type {
  CategoryOption,
  CategorySuggestion,
  ChannelInfo,
  ChannelInfoPatch,
  VideoInfo,
  VideoInfoPatch,
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

/** Les infos ACTUELLES du direct YouTube actif du compte connecté. */
export function getYoutubeStreamInfo(): Promise<VideoInfo> {
  return invoke("youtube_stream_info_get");
}

/** Les catégories YouTube disponibles (taxonomie fixe, région France). */
export function getYoutubeCategories(): Promise<CategoryOption[]> {
  return invoke("youtube_stream_info_categories");
}

/** Écrit `patch` sur le direct YouTube actif — la fusion sur le snippet complet se fait
 * côté backend (voir `youtube_channel.rs`), ce wrapper ne porte que l'appel. */
export function updateYoutubeStreamInfo(patch: VideoInfoPatch): Promise<void> {
  return invoke("youtube_stream_info_update", { patch });
}
