// A loose mirror of the engine's wire protocol (`hikari-protocol::EngineMessage`) — only
// the fields this screen actually reads (F-003 spirit: never invent a shape the wire
// hasn't sent). Not a full protocol port; extend when a screen needs another field.

/** One scene as the engine sees it, mirroring `hikari_protocol::SceneInfo`. Field names are
 * the wire's own snake_case — renaming them here would silently stop matching the JSON. */
/** Ce qu'une source vise : quelque chose de vivant à capturer, ou un fichier du disque. */
export type SourceKind =
  | "game"
  | "window"
  | "monitor"
  | "image"
  | "video"
  /** Une webcam — recréée par sa PROPRE commande, jamais comme une capture : un appareil
   * s'ouvre une fois et se partage entre les scènes qui l'affichent. */
  | "camera"
  /** Du texte écrit à l'écran. La seule famille dont le contenu vient de
   * l'utilisateur et non de la machine : ni liste à parcourir, ni fichier à
   * choisir — on l'écrit. */
  | "text";

/** Une chose capturable proposée par le moteur. `id` est la valeur exacte qu'il attend,
 * `label` est ce que l'utilisateur lit. */
export interface CaptureTarget {
  id: string;
  label: string;
}

/** Vers l'avant (dessine par-dessus) ou vers l'arrière (passe dessous). */
export type SourceOrder = "front" | "back";

/** La forme du masque appliqué à une source — miroir de `hikari_protocol::MaskShape`. Une
 * SEULE forme à la fois (2026-09-09, clarifié avec Jay : « le masque en est un [filtre] »).
 * `radius_percent` va de 0 (angles droits) à 50 (cercle inscrit dans le carré). */
export type MaskShape =
  | { kind: "none" }
  | { kind: "circle" }
  | { kind: "rounded"; radius_percent: number };

export const MASK_RADIUS_MIN = 0;
export const MASK_RADIUS_MAX = 50;

export const NO_MASK: MaskShape = { kind: "none" };

/** Les durées de fondu que le panneau propose (B7), miroir de
 * `hikari_protocol::TRANSITION_DURATIONS_MS` — un jeu fermé plutôt qu'un champ libre,
 * même raison que côté moteur : une valeur hors de ce jeu se ferait quand même clamper là-bas,
 * autant que l'écran propose seulement ce qui tient. `0` = coupe sèche, jamais un fondu à
 * durée nulle. */
export const TRANSITION_DURATIONS_MS = [0, 300, 500, 1000] as const;

/** L'étiquette que lit l'utilisateur pour chaque durée de `TRANSITION_DURATIONS_MS`. */
export const TRANSITION_DURATION_LABEL: Record<number, string> = {
  0: "Coupe sèche",
  300: "Fondu 0,3 s",
  500: "Fondu 0,5 s",
  1000: "Fondu 1 s",
};

/** Une source posée dans une scène. `kind` est l'identifiant libobs, jamais deviné.
 *
 * Porte tout ce qu'il faut pour la RECRÉER au prochain lancement : sa famille, ce qu'elle
 * capture, et où elle est posée. Ce qui manquerait ici serait un réglage à refaire à la main. */
export interface SceneSourceInfo {
  name: string;
  kind: string;
  source_kind: SourceKind;
  target_id: string;
  x: number;
  y: number;
  scale_percent: number;
  /** Figée à la souris DANS CETTE SCÈNE. Le moteur refuse alors de la saisir ; elle reste
   * visible, réordonnable et supprimable — le verrou protège du geste accidentel, jamais de
   * la décision. Par scène, car la même caméra est cadrée une fois pour toutes ici et libre
   * ailleurs. */
  locked: boolean;
  /** Pour une CAMÉRA : le fond détouré voulu par cette scène pour CETTE caméra.
   *
   * Par caméra depuis le 2026-09-06 — deux caméras d'une même scène peuvent avoir deux
   * allures. Toujours faux sur une source ordinaire. */
  background_removal: boolean;
  /** Pour une CAMÉRA : la forme de masque voulue par cette scène. Même contrat que
   * `background_removal`. */
  mask_shape: MaskShape;
  /** Montrée à l'écran, ou cachée sans être retirée (l'œil de la maquette). Cachée, la
   * source garde son cadrage, ses filtres et sa place dans la pile — c'est ce qui
   * distingue le geste du direct de la décision de retirer. */
  visible: boolean;
}

export interface SceneInfo {
  name: string;
  /** Vrai si cette scène montre AU MOINS une caméra. Lesquelles, et comment chacune est
   * cadrée et filtrée, se lit dans `sources`. */
  has_camera: boolean;
  sources: SceneSourceInfo[];
}

export interface EngineMessage {
  type: string;
  message?: string;
  scenes?: SceneInfo[];
  active?: string;
  games?: CaptureTarget[];
  windows?: CaptureTarget[];
  monitors?: CaptureTarget[];
}
