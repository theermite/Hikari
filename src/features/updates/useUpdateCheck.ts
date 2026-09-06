// La vérification du canal de mise à jour, faite UNE fois et partagée.
//
// Deux écrans en dépendent : le bandeau qui propose d'installer, et le numéro de version
// qui dit si on est à jour. Chacun appelant le canal de son côté, l'app l'interrogeait
// deux fois par lancement — et les deux pouvaient afficher des états contradictoires.
//
// La vérification part au premier montage et son résultat est mémorisé pour toute la vie
// du processus : le canal ne change pas pendant qu'une fenêtre est ouverte, et une app
// qui redemande à chaque rendu ferait du bruit réseau pour une réponse identique.

import { check } from "@tauri-apps/plugin-updater";
import { useEffect, useState } from "react";

/** La part de l'objet renvoyé par le module que ces écrans utilisent réellement. */
export interface AvailableUpdate {
  version: string;
  body?: string;
  downloadAndInstall: () => Promise<void>;
}

/** Ce que le canal a répondu.
 *
 * `unreachable` est un état à part entière, jamais confondu avec « à jour » : hors ligne
 * ou canal injoignable, on ne SAIT pas si une version existe. Afficher « à jour » là
 * serait inventer une réponse que personne n'a donnée. */
export type UpdateStatus = "checking" | "current" | "available" | "unreachable";

export interface UpdateCheck {
  status: UpdateStatus;
  update: AvailableUpdate | null;
}

/** Mémoire de processus : la promesse est créée au premier besoin, puis réutilisée. */
let pending: Promise<UpdateCheck> | null = null;

function runCheck(): Promise<UpdateCheck> {
  return check()
    .then((found) =>
      found
        ? {
            status: "available" as const,
            update: found as unknown as AvailableUpdate,
          }
        : { status: "current" as const, update: null },
    )
    .catch(() => {
      // Silencieux à l'écran côté bandeau, jamais silencieux dans les journaux : sans
      // cette trace, un canal cassé serait indistinguable d'un canal à jour.
      console.warn("[maj] canal de mise à jour injoignable");
      return { status: "unreachable" as const, update: null };
    });
}

export function useUpdateCheck(): UpdateCheck {
  const [result, setResult] = useState<UpdateCheck>({
    status: "checking",
    update: null,
  });

  useEffect(() => {
    let cancelled = false;
    pending ??= runCheck();
    pending.then((found) => {
      if (!cancelled) setResult(found);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return result;
}

/** Oublie le résultat mémorisé — réservé aux tests, qui rejouent plusieurs canaux. */
export function forgetUpdateCheck(): void {
  pending = null;
}
