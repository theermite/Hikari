// Ce qu'il reste à faire avant de passer en direct, lu dans l'état RÉEL du moteur.
//
// La maquette pose une carte « Préparation » qui n'apparaît que dans cette disposition :
// le kit de marque, puis « Sources à vérifier » avec des points verts et rouges. Elle en
// montre trois, inventés. Ceux d'ici sont mesurés — un point vert qui ne regarde rien
// serait pire qu'aucun point : il rassurerait sans preuve.
//
// Fonctions PURES : elles lisent des scènes déjà reçues. Vérifiables sans moteur, et donc
// vérifiables tout court, puisque le moteur ne se lance pas dans un test.

import type { SceneInfo } from "./types";

/** L'état d'un point de contrôle. Trois valeurs, jamais deux : « on ne sait pas » n'est
 * pas « c'est bon », et le confondre est exactement ce qui fait démarrer un direct sur une
 * scène vide. */
export type CheckState = "ok" | "attention" | "inconnu";

export interface PrepCheck {
  id: string;
  /** Ce qu'on vérifie, en une ligne lisible. */
  label: string;
  state: CheckState;
  /** Ce qu'il faut faire quand ça n'est pas bon. Vide quand tout va bien. */
  fix: string;
}

/** Les points de contrôle, calculés sur les scènes et celle qui est en direct. */
export function prepChecks(
  scenes: SceneInfo[] | null,
  active: string | null,
): PrepCheck[] {
  // Rien reçu du moteur : tout est INCONNU, jamais « bon ». C'est le seul honnête.
  if (scenes === null || active === null) {
    return [
      inconnu("scene", "La scène en direct a du contenu"),
      inconnu("camera", "Une caméra est posée"),
      inconnu("sources", "Toutes les sources sont visibles"),
    ];
  }
  const live = scenes.find((scene) => scene.name === active);
  const sources = live?.sources ?? [];
  const camera = sources.filter((source) => source.source_kind === "camera");
  const cachees = sources.filter((source) => !source.visible);

  return [
    {
      id: "scene",
      label: live
        ? `« ${live.name} » est en direct`
        : "La scène en direct a du contenu",
      state: sources.length > 0 ? "ok" : "attention",
      fix:
        sources.length > 0 ? "" : "Ajoute au moins une source à cette scène.",
    },
    {
      id: "camera",
      label:
        camera.length > 0
          ? `${camera.length} caméra${camera.length > 1 ? "s" : ""} posée${camera.length > 1 ? "s" : ""}`
          : "Une caméra est posée",
      // Une scène sans caméra est un choix légitime — un écran d'attente, un partage
      // d'écran. Ce point RENSEIGNE, il ne réprimande pas.
      state: camera.length > 0 ? "ok" : "inconnu",
      fix: camera.length > 0 ? "" : "Aucune caméra ici — voulu, ou oublié ?",
    },
    {
      id: "sources",
      label:
        cachees.length > 0
          ? `${cachees.length} source${cachees.length > 1 ? "s" : ""} cachée${cachees.length > 1 ? "s" : ""}`
          : "Toutes les sources sont visibles",
      state: cachees.length > 0 ? "attention" : "ok",
      // Une source cachée oubliée est LE piège du direct : elle ne manque à personne
      // jusqu'à ce que les spectateurs la réclament.
      fix:
        cachees.length > 0
          ? `Cachée${cachees.length > 1 ? "s" : ""} : ${cachees.map((s) => s.name).join(", ")}`
          : "",
    },
  ];
}

function inconnu(id: string, label: string): PrepCheck {
  return {
    id,
    label,
    state: "inconnu",
    fix: "Le moteur n'a pas encore répondu.",
  };
}
