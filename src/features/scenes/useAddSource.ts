// La fenêtre d'ajout d'une source : ce qu'elle propose, et ce qui se passe au choix —
// extrait de ScenesPanel.tsx le 2026-09-08 (ce fichier dépassait déjà le plafond BLOQUANT
// de 500 lignes avant ce soir ; ajouter la fenêtre de réglages séparée sans découper aurait
// aggravé une dette déjà présente).

import { open } from "@tauri-apps/plugin-dialog";
import { useEffect, useRef, useState } from "react";
import { addCameraSource, listCameras } from "../camera/api";
import type { CaptureTargets } from "./AddSourceModal";
import { addCaptureSource, listCaptureTargets } from "./api";
import { FILE_FILTERS, nameFromPath, SOURCE_FAMILIES } from "./sourcePicker";
import type { CaptureTarget, SceneInfo, SourceKind } from "./types";

interface State {
  status: string;
  scenes?: SceneInfo[];
}

export function useAddSource(
  state: State,
  addingTo: string | null,
  setAddingTo: (name: string | null) => void,
  setActionError: (message: string | null) => void,
) {
  /** Ce que le MOTEUR diffuse : les captures vivantes, sans les caméras (il les détecte
   * par une commande à part). Garder ici sa forme exacte évite d'inventer un champ vide
   * que rien ne remplit. */
  const [targets, setTargets] = useState<Omit<
    CaptureTargets,
    "cameras"
  > | null>(null);
  /** Les caméras branchées, telles que la machine les rapporte. Elles arrivent par une
   * commande à part (le moteur les DÉTECTE, il ne les diffuse pas avec les captures), d'où
   * cet état distinct recomposé avec le reste juste avant l'affichage. */
  const [cameras, setCameras] = useState<CaptureTarget[]>([]);
  const [targetsError, setTargetsError] = useState<string | null>(null);
  const [chosenFamily, setFamily] = useState<SourceKind>("game");
  const [search, setSearch] = useState("");
  /** Le texte en cours de saisie dans la fenêtre d'ajout. */
  const [draftText, setDraftText] = useState("");
  const chosenIsFile =
    SOURCE_FAMILIES.find((f) => f.kind === chosenFamily)?.isFile ?? false;
  const searchInput = useRef<HTMLInputElement>(null);

  // Redemandée à chaque ouverture du choix, jamais mise en cache : un jeu lancé entre-temps
  // doit apparaître sans rien redémarrer.
  //
  // L'échec est DIT, jamais avalé : le moteur ne tourne qu'avec le panneau Aperçu ouvert, et
  // afficher « Recherche en cours… » pour toujours laisse l'utilisateur attendre une liste
  // qui ne viendra jamais (même défaut que le panneau Audio, corrigé le 2026-08-04).
  useEffect(() => {
    if (!addingTo) return;
    setTargetsError(null);
    listCaptureTargets().catch(() =>
      setTargetsError(
        "Le moteur n'est pas démarré — ouvre le panneau Aperçu, la liste apparaîtra toute seule.",
      ),
    );
    // Redemandées à chaque ouverture, comme les captures : une webcam branchée entre-temps
    // doit apparaître sans rien redémarrer. Un échec laisse simplement la famille vide —
    // il est déjà dit par le message ci-dessus, qui a la même cause (moteur éteint).
    listCameras()
      .then((devices) =>
        setCameras(
          devices.map((device) => ({
            id: device.device_id,
            label: device.name,
          })),
        ),
      )
      .catch(() => setCameras([]));
  }, [addingTo]);

  useEffect(() => {
    if (addingTo && targets && !chosenIsFile) searchInput.current?.focus();
  }, [addingTo, targets, chosenIsFile]);

  /** Les appareils que la scène en cours d'ajout montre DÉJÀ. */
  const placedCameraIds = new Set(
    (state.status === "ready" ? (state.scenes ?? []) : [])
      .find((scene) => scene.name === addingTo)
      ?.sources.filter((source) => source.source_kind === "camera")
      .map((source) => source.target_id) ?? [],
  );

  /** Ce que la fenêtre d'ajout propose : les captures du moteur, plus les caméras que
   * cette scène ne montre pas encore. Reproposer une caméra déjà posée n'ouvrirait rien de
   * neuf, et provoquerait un refus qu'on peut simplement ne pas déclencher. */
  const pickerTargets: CaptureTargets | null = targets && {
    ...targets,
    cameras: cameras.filter((camera) => !placedCameraIds.has(camera.id)),
  };

  const addToScene = (
    scene: string,
    kind: SourceKind,
    target: CaptureTarget,
  ) => {
    setActionError(null);
    setAddingTo(null);
    // Une caméra est UN appareil physique partagé entre les scènes : `add_capture_source`
    // l'ouvrirait une seconde fois. Le moteur a sa propre commande pour ça (ADR : un
    // appareil = une source libobs), et le nom vient de l'appareil, jamais de nous.
    if (kind === "camera") {
      addCameraSource(target.id, scene).catch((error: unknown) =>
        setActionError(String(error)),
      );
      return;
    }
    // Le libellé lisible sert de nom dans la scène : c'est ce que l'utilisateur reconnaît,
    // et le moteur refuse un doublon.
    addCaptureSource(scene, kind, target.id, target.label).catch(
      (error: unknown) => setActionError(String(error)),
    );
  };

  /** Pose un texte dans la scène. Le texte SERT DE CIBLE et de nom : c'est ce que
   * l'utilisateur reconnaîtra dans sa liste de sources, sans avoir à le nommer une
   * seconde fois. */
  const addText = (scene: string, texte: string) => {
    setActionError(null);
    setAddingTo(null);
    setDraftText("");
    addCaptureSource(scene, "text", texte, texte).catch((error: unknown) =>
      setActionError(String(error)),
    );
  };

  /** Ouvre le sélecteur du système, puis pose le fichier choisi dans la scène. Un abandon
   * (aucun fichier retenu) ne fait rien et ne dit rien : ce n'est pas une erreur. */
  const pickFile = (scene: string, kind: SourceKind) => {
    setActionError(null);
    open({
      multiple: false,
      filters: [
        {
          name: kind === "image" ? "Images" : "Vidéos",
          extensions: FILE_FILTERS[kind] ?? [],
        },
      ],
    })
      .then((path) => {
        if (typeof path !== "string") return;
        setAddingTo(null);
        return addCaptureSource(scene, kind, path, nameFromPath(path));
      })
      .catch((error: unknown) => setActionError(String(error)));
  };

  return {
    targets,
    setTargets,
    targetsError,
    setTargetsError,
    chosenFamily,
    setFamily,
    search,
    setSearch,
    draftText,
    setDraftText,
    chosenIsFile,
    searchInput,
    pickerTargets,
    addToScene,
    addText,
    pickFile,
  };
}
