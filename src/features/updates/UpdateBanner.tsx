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

import { relaunch } from "@tauri-apps/plugin-process";
import { check } from "@tauri-apps/plugin-updater";
import { useEffect, useState } from "react";

/** La part de l'objet renvoyé par le module que cet écran utilise réellement. */
interface AvailableUpdate {
  version: string;
  body?: string;
  downloadAndInstall: () => Promise<void>;
}

type Phase = "idle" | "installing" | "failed";

export function UpdateBanner() {
  const [update, setUpdate] = useState<AvailableUpdate | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");

  useEffect(() => {
    let cancelled = false;
    check()
      .then((found) => {
        if (!cancelled && found) setUpdate(found as unknown as AvailableUpdate);
      })
      .catch(() => {
        // Silencieux à l'écran, jamais silencieux dans les journaux : sans cette trace,
        // un canal cassé serait indistinguable d'un canal à jour (Observability).
        console.warn("[maj] canal de mise à jour injoignable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!update) return null;

  async function install() {
    if (!update) return;
    setPhase("installing");
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
        onClick={() => setUpdate(null)}
        className="rounded px-3 py-1 text-amber-200/80 hover:text-amber-100"
      >
        Plus tard
      </button>
    </div>
  );
}
