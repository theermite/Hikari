// Bandeau de mise à jour — l'app annonce une nouvelle version et l'installe SUR CLIC.
//
// Pourquoi un bandeau et pas une installation automatique : une mise à jour qui se lance
// seule peut couper un live. Ici, Jay décide du moment (Dignity — choix réel, jamais un
// faux choix ni une action subie). « Plus tard » est un vrai refus : rien ne se passe, et
// la proposition revient au prochain lancement.
//
// Pourquoi les pannes du canal sont silencieuses à l'écran : hors ligne, canal privé
// injoignable ou adresse absente (cas du dépôt public, qui n'embarque aucune adresse
// privée), le cockpit doit démarrer exactement comme d'habitude. Une panne du canal de
// mise à jour n'est jamais une panne de l'app.

import { invoke } from "@tauri-apps/api/core";
import { relaunch } from "@tauri-apps/plugin-process";
import { useState } from "react";
import { useUpdateCheck } from "./useUpdateCheck";

type Phase = "idle" | "installing" | "failed";

export function UpdateBanner() {
  // La vérification est partagée avec le numéro de version affiché en haut du cockpit :
  // un seul appel au canal, et deux écrans qui ne peuvent pas se contredire.
  const { update } = useUpdateCheck();
  const [phase, setPhase] = useState<Phase>("idle");
  // « Plus tard » est un vrai refus, et il n'appartient qu'à ce bandeau : le numéro de
  // version en haut du cockpit continue d'annoncer la version disponible, sinon écarter
  // le bandeau reviendrait à effacer l'information au lieu de la remettre à plus tard.
  const [dismissed, setDismissed] = useState(false);

  if (!update || dismissed) return null;

  async function install() {
    if (!update) return;
    setPhase("installing");

    // Fermer le moteur AVANT d'installer. L'installeur ferme l'application, mais le
    // moteur vidéo est un processus SÉPARÉ (ADR-013) qu'il ne connaît pas : il garde
    // ouvertes les bibliothèques vidéo, et Windows refuse alors de les remplacer.
    // Vécu le 2026-09-04 — « Error opening file for writing: avcodec-61.dll ».
    // L'échec n'interrompt rien : le moteur ne démarre qu'à la demande, donc « rien à
    // arrêter » est un cas normal, pas une panne.
    try {
      await invoke("stop_engine");
    } catch {
      console.warn(
        "[maj] arrêt du moteur impossible — installation poursuivie",
      );
    }

    try {
      await update.downloadAndInstall();
    } catch {
      // L'annonce RESTE affichée : l'utilisateur doit pouvoir réessayer, et savoir
      // pourquoi rien ne s'est passé. Effacer le bandeau ici ferait disparaître la panne
      // au lieu de la dire.
      setPhase("failed");
      return;
    }
    await relaunch();
  }

  return (
    <div className="hikari-update-banner flex items-center gap-3 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm">
      <span className="flex-1 text-amber-100">
        Hikari <strong>{update.version}</strong> est disponible.
        {update.body ? (
          <span className="text-amber-200/70"> — {update.body}</span>
        ) : null}
      </span>

      {phase === "failed" ? (
        <span role="alert" className="text-red-300">
          Le téléchargement a échoué. Vérifie ta connexion, puis réessaie.
        </span>
      ) : null}

      <button
        type="button"
        onClick={install}
        disabled={phase === "installing"}
        className="rounded bg-amber-500 px-3 py-1 font-medium text-black disabled:opacity-60"
      >
        {phase === "installing" ? "Installation…" : "Mettre à jour"}
      </button>

      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="rounded px-3 py-1 text-amber-200/80 hover:text-amber-100"
      >
        Plus tard
      </button>
    </div>
  );
}
