// EngineErrorBanner — ce que le moteur REFUSE, dit à voix haute, une seule fois pour tout
// le cockpit.
//
// Pourquoi ici et pas dans chaque panneau (2026-09-06) : le moteur répond de façon
// asynchrone, longtemps après le clic, et souvent pendant qu'un AUTRE panneau est au
// premier plan. Un refus affiché dans le panneau d'origine est donc un refus que personne
// ne lit. Trois panneaux écoutaient déjà `error` chacun de leur côté, et le seul chemin qui
// en avait vraiment besoin — l'ajout et le retrait d'une caméra — n'écoutait pas : le clic
// ne faisait rien, en silence, et il était impossible de dire si l'échec venait du matériel
// ou du logiciel (Jay, 2026-09-06 : « la 3ᵉ caméra ne s'ajoute pas »).
//
// Ce bandeau ne montre QUE ce que le moteur a dit. Il ne traduit pas, ne devine pas une
// cause, et ne propose pas de correctif : un message inventé serait pire que le silence.

import { listen } from "@tauri-apps/api/event";
import { useEffect, useState } from "react";

interface EngineMessage {
  type: string;
  message?: string;
  id?: string;
}

/** Le refus affiché. `seq` distingue deux refus au texte IDENTIQUE : sans lui, refaire le
 * geste qui vient d'échouer ne rallumerait pas le bandeau qu'on vient de fermer, et le
 * second échec passerait sous silence — exactement ce que ce composant supprime. */
interface Refusal {
  text: string;
  seq: number;
}

export function EngineErrorBanner() {
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  // Une INFORMATION, pas un refus. Elle vit a part parce qu'elle ne se dit pas avec les
  // memes mots : « Le moteur a refuse » sur « ta cle servira au prochain direct » ferait
  // chercher une panne la ou tout va bien.
  const [notice, setNotice] = useState<Refusal | null>(null);

  useEffect(() => {
    let noticeSeq = 0;
    const unlistenNotice = listen<string>("engine-notice", (event) => {
      noticeSeq += 1;
      setNotice({ text: event.payload, seq: noticeSeq });
    });
    let seq = 0;
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "error" && msg.message) {
        seq += 1;
        setRefusal({ text: msg.message, seq });
      }
      // Un échec sur UNE plateforme (B3) ne tue pas les autres, donc le moteur le rapporte
      // à part. Pour l'utilisateur c'est le même événement : quelque chose a été refusé.
      if (msg.type === "platform_error" && msg.message) {
        seq += 1;
        setRefusal({ text: `${msg.id ?? "plateforme"} — ${msg.message}`, seq });
      }
    });
    return () => {
      unlisten.then((f) => f());
      unlistenNotice.then((f) => f());
    };
  }, []);

  // Un refus passe DEVANT une information : si les deux sont la, c'est le refus qu'il faut
  // lire d'abord.
  if (!refusal && notice) {
    return (
      <div
        role="status"
        className="mx-2.5 mt-2.5 flex items-start justify-between gap-3 rounded-hikari border border-hikari-accent/40 bg-hikari-accent/10 px-4 py-2.5"
      >
        <p className="text-[12.5px] text-hikari-txt">{notice.text}</p>
        <button
          type="button"
          onClick={() => setNotice(null)}
          aria-label="Fermer ce message"
          className="shrink-0 px-1 text-hikari-txt-faint transition hover:text-hikari-txt"
        >
          ✕
        </button>
      </div>
    );
  }

  if (!refusal) return null;

  return (
    <div
      role="alert"
      className="mx-2.5 mt-2.5 flex items-start justify-between gap-3 rounded-hikari border border-hikari-red/40 bg-hikari-red/10 px-4 py-2.5"
    >
      <p className="text-[12.5px] text-hikari-txt">
        <span className="mr-1.5 font-medium text-hikari-red">
          Le moteur a refusé :
        </span>
        {refusal.text}
      </p>
      <button
        type="button"
        onClick={() => setRefusal(null)}
        aria-label="Fermer ce message"
        className="shrink-0 px-1 text-hikari-txt-faint transition hover:text-hikari-txt"
      >
        ✕
      </button>
    </div>
  );
}
