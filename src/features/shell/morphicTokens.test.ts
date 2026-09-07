// Tests écrits AVANT le code (TDG).
//
// Ce que ça règle, vu par Jay le 2026-09-07 : « le thème clair et le thème sombre ne
// changent rien, les polices ne changent pas, la densité non plus ». Le module posait bien
// ses réglages ; l'apparence d'Hikari ne les écoutait pas.
//
// POURQUOI le thème clair compte ici, et j'avais tort de le croire secondaire : sur un
// outil de stream, un écran clair ÉCLAIRE le visage de celui qui filme. Jay n'a pas de
// lampes de studio et ouvre déjà un bloc-notes en plein écran pour s'éclairer (note du
// 2026-09-06, « panneaux d'éclairage virtuels »). Le thème clair est une fonction du
// produit, pas un confort.
//
// Ce fichier ne teste PAS des couleurs — une couleur se juge à l'œil. Il teste que la
// feuille de style DÉCLARE bien une réponse pour chaque réglage que le module peut poser.
// Sans cela, un axe reste muet et le panneau ment sur ce qu'il propose.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// La feuille est lue sur le DISQUE et non importée : Vitest neutralise les feuilles de
// style, donc un import rendrait une chaîne vide — et le test passerait au vert sur du
// néant. Un test qui ne peut pas échouer ne garde rien.
const css = readFileSync(join(process.cwd(), "src/index.css"), "utf-8");

/** Les valeurs que le module peut poser sur `<html>`, lues dans sa source
 * (`morphic-adapter` 2.0.0-beta.1) et non supposées. */
const THEMES_A_COUVRIR = ["light", "sepia", "high-contrast"];
const POLICES_A_COUVRIR = ["system", "serif", "atkinson", "dyslexic"];

describe("index.css répond aux réglages du module d'adaptation", () => {
  it.each(THEMES_A_COUVRIR)("should_answer_the_%s_theme", (theme) => {
    // « sepia » et « high-contrast » sont déjà rendus par un filtre du module. Hikari
    // doit quand même les nommer : le filtre s'applique sur une palette SOMBRE, et
    // teinter du presque-noir ne donne pas du sépia.
    expect(css).toContain(`[data-morphic-theme="${theme}"]`);
  });

  it("should_follow_the_system_when_the_theme_is_left_on_auto", () => {
    // « auto » ne se traduit pas en couleurs : il délègue au réglage de la machine. Sans
    // cette règle, choisir « auto » sur un système clair garderait Hikari sombre.
    expect(css).toContain("prefers-color-scheme: light");
  });

  it.each(POLICES_A_COUVRIR)("should_answer_the_%s_font", (police) => {
    expect(css).toContain(`[data-morphic-font-family="${police}"]`);
  });

  it("should_consume_the_density_multiplier_the_module_publishes", () => {
    // Le module publie `--morphic-gap` et laisse l'application s'en servir. Ne pas le
    // consommer rend le réglage muet — c'est exactement ce que Jay a constaté.
    expect(css).toContain("--morphic-gap");
  });

  it("should_route_the_font_through_the_hikari_token", () => {
    // La correction tient en un point : `--font-hikari` suit le module, donc TOUT ce qui
    // utilise le jeton suit aussi. Redéclarer la police sur chaque écran serait la même
    // duplication qui a fait diverger le reste.
    expect(css).toMatch(
      /\[data-morphic-font-family=[^\]]+\][^{]*\{\s*--font-hikari/,
    );
  });

  it("should_ship_every_font_it_offers", () => {
    // Jay, 2026-09-07 : « es-tu sûr qu'Atkinson et OpenDyslexic sont bien les polices qui
    // s'affichent ? » Elles ne l'étaient pas. Les noms étaient cités dans la feuille de
    // style, les fichiers n'étaient nulle part, et ni l'une ni l'autre n'est installée sur
    // Windows — choisir « Atkinson » donnait Verdana, « OpenDyslexic » donnait Comic Sans.
    //
    // Une option d'accessibilité qui livre autre chose que ce qu'elle annonce est pire
    // qu'une option absente : elle fait croire au besoin couvert. Ce test lie donc les deux
    // faits — ce que la feuille PROPOSE, et ce que l'application EMBARQUE.
    const main = readFileSync(join(process.cwd(), "src/main.tsx"), "utf-8");
    const policesCitees = [
      ["Atkinson Hyperlegible", "@fontsource/atkinson-hyperlegible"],
      ["OpenDyslexic", "@fontsource/opendyslexic"],
    ] as const;

    for (const [famille, paquet] of policesCitees) {
      if (!css.includes(famille)) continue;
      expect(
        main.includes(paquet),
        `la feuille propose « ${famille} » : le paquet ${paquet} doit être embarqué`,
      ).toBe(true);
    }
  });
});
