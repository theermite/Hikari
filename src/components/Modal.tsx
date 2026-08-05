// Fenêtre modale — `<dialog>` natif, zéro dépendance ajoutée.
//
// POURQUOI le natif et pas une librairie : `showModal()` place l'élément dans la couche
// supérieure du navigateur, une couche gérée par le moteur de rendu lui-même. Aucun
// repositionnement JavaScript, aucun nœud déplacé dans le document. C'est précisément ce qui
// a cassé en silence ici avec le glisser-déposer de dockview (écran blanc, cause jamais
// trouvée) — la modale native ne fait rien de cette famille, elle ne peut donc pas rencontrer
// ce bug. Le navigateur fournit en prime le confinement du focus et la fermeture par Échap.

import { type ReactNode, useEffect, useId, useRef } from "react";

interface ModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Modal({ open, title, onClose, children }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      // Mémorisé AVANT l'ouverture : c'est là qu'il faudra rendre le focus, sinon il
      // retombe sur le corps du document et l'utilisateur au clavier est perdu.
      opener.current = document.activeElement as HTMLElement | null;
      dialog.showModal();
      dialog.querySelector<HTMLElement>("[data-autofocus]")?.focus();
      document.body.style.overflow = "hidden";
    }
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const close = () => {
    document.body.style.overflow = "";
    opener.current?.focus();
    onClose();
  };

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={close}
      // Échap : le navigateur ferme seul, on resynchronise l'état React.
      onCancel={close}
      // Fermeture au clic extérieur, faite par le NAVIGATEUR : `closedby="any"` remplace le
      // gestionnaire de clic qu'on écrivait à la main, donc zéro JavaScript pour ça. Sur un
      // navigateur qui ne connaît pas encore l'attribut, Échap et le bouton Fermer restent —
      // la dégradation ne casse rien.
      {...{ closedby: "any" }}
      className="m-auto w-[420px] max-w-[92vw] rounded-[10px] border border-hikari-line bg-hikari-bg-3 p-0 text-hikari-txt backdrop:bg-black/60"
    >
      <div className="flex items-center justify-between gap-3 border-b border-hikari-line px-4 py-3">
        <h2 id={titleId} className="truncate text-[13px] font-medium">
          {title}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label="Fermer"
          className="h-6 w-6 shrink-0 rounded-[6px] border border-hikari-line text-[12px] text-hikari-txt-dim transition hover:border-hikari-accent hover:text-hikari-txt"
        >
          ✕
        </button>
      </div>
      <div className="flex max-h-[70vh] flex-col gap-5 overflow-y-auto p-4">
        {children}
      </div>
    </dialog>
  );
}
