// Bouton « Préréglage » de la barre du direct — ouvre les infos de stream (F-054,
// Twitch + YouTube). Déplacé du panneau cockpit fixe « Infos direct » le 2026-09-19
// (Jay : « ça encombre l'interface, ça peut se trouver dans le Pré-vol ou la barre du
// haut ») — choix du haut, ce bouton portait déjà exactement cette promesse à l'état de
// `ComingSoon` (« choisir un préréglage de direct — plateformes, scènes, titre »).
//
// Réutilise la modale native déjà écrite (`components/Modal.tsx`) plutôt que d'inventer
// un second mécanisme d'ouverture/fermeture — elle porte déjà la suppression de l'Aperçu
// pendant qu'une modale est ouverte (l'aperçu natif se dessine toujours au-dessus du web,
// voir l'en-tête de `Modal.tsx`), un mur que ce popover aurait sinon dû redécouvrir.
//
// Plateformes et scènes (le reste de la promesse « préréglage ») restent hors de ce
// popover : aucune des deux n'a encore de brique côté moteur (même limite déjà notée dans
// le `ComingSoon` d'origine) — seules les infos de stream, déjà câblées, y entrent.

import { useState } from "react";
import { Modal } from "../../components/Modal";
import { TwitchSection } from "../streaminfo/TwitchSection";
import { YoutubeSection } from "../streaminfo/YoutubeSection";

export function PresetPopover() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 rounded-full border border-hikari-line px-3 py-1.5 text-[12.5px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
      >
        Préréglage <span className="font-medium text-hikari-txt">—</span> ▾
      </button>
      <Modal open={open} title="Infos direct" onClose={() => setOpen(false)}>
        {/* Montés seulement à l'ouverture : `Modal` rend ses enfants même fermée
            (`<dialog>` non affiché n'est pas démonté), et chaque section lit Twitch/
            YouTube dès son montage — sans cette garde, un simple survol du cockpit
            déclencherait ces appels réseau avant même un clic sur le bouton. */}
        {open ? (
          <>
            <TwitchSection />
            <div className="border-t border-hikari-line pt-4">
              <YoutubeSection />
            </div>
          </>
        ) : null}
      </Modal>
    </>
  );
}
