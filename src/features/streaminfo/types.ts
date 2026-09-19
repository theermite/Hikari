// Types F-054 — miroir des structures Rust (`accounts::twitch_channel`,
// `accounts::youtube_channel`), aucune redéfinition de logique côté interface : la
// validation vit dans le backend (`validate_patch`), ce module ne fait que nommer la
// forme des données.

export interface ChannelInfo {
  title: string;
  game_id: string;
  game_name: string;
  tags: string[];
}

export interface CategorySuggestion {
  id: string;
  name: string;
  box_art_url: string;
}

/** Miroir de `ChannelInfoPatch` côté Rust — un champ absent (`undefined`) ne touche pas
 * la valeur Twitch, exactement le contrat que `#[serde(skip_serializing_if)]` porte côté
 * backend. */
export interface ChannelInfoPatch {
  title?: string;
  game_id?: string;
  tags?: string[];
}

/** Miroir de `youtube_channel::VideoInfo`. */
export interface VideoInfo {
  title: string;
  description: string;
  category_id: string;
  tags: string[];
}

/** Miroir de `youtube_channel::CategoryOption` — taxonomie fixe YouTube, pas une
 * recherche libre comme côté Twitch. */
export interface CategoryOption {
  id: string;
  name: string;
}

/** Miroir de `youtube_channel::VideoInfoPatch` — même contrat « champ absent = pas
 * touché » que côté Twitch, même si la fusion elle-même se fait côté backend sur le
 * snippet complet (YouTube ne connaît pas le PATCH partiel, voir `youtube_channel.rs`). */
export interface VideoInfoPatch {
  title?: string;
  description?: string;
  category_id?: string;
  tags?: string[];
}
