// @vitest-environment jsdom
//
// Tests écrits AVANT le code (TDG).
//
// Ce que ça règle, vu par Jay le 2026-09-07 : le panneau d'adaptation s'ouvre enfin, et
// l'aperçu passe DEVANT lui. L'aperçu n'est pas du contenu web — c'est la fenêtre native du
// moteur, greffée dans celle de l'app. Une fenêtre native se dessine toujours au-dessus du
// web, quel que soit l'empilement.
//
// Le mécanisme de retrait existait déjà (`suppression.ts`) et les fenêtres surgissantes
// écrites ici s'en servent. Le panneau d'adaptation vient d'un module externe : il ne peut
// pas s'annoncer, et sa version 2.0.0-beta.1 n'expose aucun signal d'ouverture.
//
// D'où l'observation du DOM : on regarde si le panneau EST là, plutôt que d'écouter les
// clics. Écouter les clics raterait la fermeture au clavier, la fermeture par clic à côté,
// et tout chemin que le module ajouterait demain.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { watchForOverlay } from "./domSuppression";
import { isPreviewSuppressed, resetPreviewSuppression } from "./suppression";

const SELECTEUR = ".morphic-mb-modal";

function ouvrirPanneau(): HTMLElement {
  const el = document.createElement("div");
  el.className = "morphic-mb-modal";
  document.body.appendChild(el);
  return el;
}

/** Les observateurs de mutation sont livrés en micro-tâche : il faut la laisser passer. */
async function laisserObserver() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

beforeEach(() => {
  resetPreviewSuppression();
  document.body.innerHTML = "";
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("watchForOverlay", () => {
  it("should_hide_the_preview_when_the_overlay_appears", async () => {
    const stop = watchForOverlay(SELECTEUR);
    expect(isPreviewSuppressed()).toBe(false);

    ouvrirPanneau();
    await laisserObserver();

    expect(isPreviewSuppressed()).toBe(true);
    stop();
  });

  it("should_show_the_preview_again_when_the_overlay_goes_away", async () => {
    const stop = watchForOverlay(SELECTEUR);
    const panneau = ouvrirPanneau();
    await laisserObserver();

    panneau.remove();
    await laisserObserver();

    expect(isPreviewSuppressed()).toBe(false);
    stop();
  });

  it("should_hide_the_preview_when_the_overlay_is_already_there_on_start", async () => {
    // Un rechargement de la page pendant que le panneau est ouvert n'arrive pas souvent,
    // mais l'aperçu resterait alors devant lui sans qu'aucune mutation ne le signale.
    ouvrirPanneau();

    const stop = watchForOverlay(SELECTEUR);

    expect(isPreviewSuppressed()).toBe(true);
    stop();
  });

  it("should_release_its_hold_when_the_watch_stops", async () => {
    const stop = watchForOverlay(SELECTEUR);
    ouvrirPanneau();
    await laisserObserver();

    stop();

    expect(isPreviewSuppressed()).toBe(false);
  });

  it("should_count_one_hold_no_matter_how_many_times_the_overlay_is_seen", async () => {
    // Une mutation voisine redéclenche l'observateur alors que le panneau n'a pas bougé.
    // Sans garde, chaque passage prendrait une demande de plus, et l'aperçu ne
    // reviendrait JAMAIS — le compteur ne retomberait pas à zéro.
    const stop = watchForOverlay(SELECTEUR);
    const panneau = ouvrirPanneau();
    await laisserObserver();
    document.body.appendChild(document.createElement("span"));
    await laisserObserver();

    panneau.remove();
    await laisserObserver();

    expect(isPreviewSuppressed()).toBe(false);
    stop();
  });
});
