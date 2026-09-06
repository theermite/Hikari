// La barre de titre de Hikari — la nôtre, à la place de celle de Windows.
//
// Demandé par Jay le 2026-09-06 : la barre système posait un bandeau gris étranger
// au-dessus d'un cockpit entièrement dessiné. Elle disparaît (`decorations: false`), et les
// trois gestes qu'elle portait rentrent dans l'application.
//
// Ce qu'il ne faut pas perdre en route, et qui est traité ici :
//   — DÉPLACER la fenêtre. Sans bordure système, ce geste n'existe plus tout seul : c'est
//     `data-tauri-drag-region` qui le rend, et il doit couvrir toute la zone vide ;
//   — CLIQUER les boutons. Un bouton posé DANS la zone de déplacement se fait voler son
//     clic par le geste de déplacement — la fenêtre bouge, le bouton ne répond pas.

import { getCurrentWindow } from "@tauri-apps/api/window";

const BUTTON =
  "grid h-full w-11 place-items-center text-hikari-txt-dim transition hover:bg-hikari-line hover:text-hikari-txt";

export function TitleBar() {
  // La fenêtre est demandée AU CLIC, jamais au dessin : `getCurrentWindow()` a besoin du
  // système autour de l'application, et l'appeler pendant le rendu faisait tomber tout
  // affichage hors de ce système — le rendu des tests, et le premier instant avant que le
  // système ne réponde.
  return (
    <div className="flex h-8 flex-shrink-0 items-stretch bg-hikari-canvas">
      {/* Toute la zone vide déplace la fenêtre : c'est le seul geste que la barre système
      rendait et que rien d'autre ne remplace. */}
      {/* Nue, volontairement : la barre latérale porte déjà le nom et la devise, juste
      en dessous. L'écrire ici le dirait deux fois dans les deux premiers centimètres de
      la fenêtre. */}
      <div data-tauri-drag-region className="flex-1" />
      {/* Hors de la zone de déplacement, volontairement. */}
      <div className="flex items-stretch">
        <button
          type="button"
          aria-label="Réduire la fenêtre"
          onClick={() => getCurrentWindow().minimize()}
          className={BUTTON}
        >
          {/* Un trait, comme partout ailleurs sur ce système : la forme est apprise, la
          réinventer obligerait à la deviner. */}
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <title>Réduire</title>
            <path d="M0 5h10" stroke="currentColor" strokeWidth="1" />
          </svg>
        </button>
        <button
          type="button"
          aria-label="Agrandir ou restaurer la fenêtre"
          onClick={() => getCurrentWindow().toggleMaximize()}
          className={BUTTON}
        >
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <title>Agrandir</title>
            <rect
              x="0.5"
              y="0.5"
              width="9"
              height="9"
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
            />
          </svg>
        </button>
        <button
          type="button"
          aria-label="Fermer la fenêtre"
          onClick={() => getCurrentWindow().close()}
          // Le rouge est réservé à CE bouton : c'est le seul dont le geste ne se rattrape
          // pas d'un clic.
          className={`${BUTTON} hover:bg-hikari-red hover:text-white`}
        >
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <title>Fermer</title>
            <path
              d="M0 0l10 10M10 0L0 10"
              stroke="currentColor"
              strokeWidth="1"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
