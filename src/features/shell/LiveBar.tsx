// LiveBar — la barre qui répond à « est-ce que je diffuse, là ? ».
//
// Jay, 2026-09-04 : « en regardant le cockpit, tu ne sais pas si tu diffuses ». Le moteur
// savait démarrer une diffusion depuis la brique B2a ; l'application, elle, n'exposait
// aucun bouton pour le lui demander. Cette barre ferme les deux manques d'un coup.
//
// Elle n'affiche QUE ce que le moteur rapporte. Pas de compteur de spectateurs tant que
// les plateformes ne sont pas branchées : un zéro à la place d'une donnée absente ment
// plus qu'il n'informe.
//
// L'état ne bascule JAMAIS de façon optimiste. Cliquer « Démarrer » envoie la demande et
// attend le message `started` du moteur. Basculer tout de suite afficherait « en direct »
// alors que la diffusion vient d'échouer — le pire mensonge possible sur cet écran.

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useEffect, useState } from "react";
import { Badge } from "../../components/ui/Badge";

/** Les seuls messages moteur que cette barre lit. */
type EngineMessage =
  | { type: "started" }
  | { type: "stream_stopped" }
  | { type: "frames"; dropped: number; total: number }
  | { type: "error"; message: string }
  | { type: string };

/** `h:mm:ss` — la forme d'une durée de direct, qui dépasse volontiers l'heure. */
export function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function LiveBar() {
  const [liveSince, setLiveSince] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [dropped, setDropped] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "started") {
        setLiveSince(Date.now());
        setDropped(null);
        setError(null);
        setPending(false);
      }
      if (msg.type === "stream_stopped") {
        setLiveSince(null);
        setPending(false);
      }
      if (msg.type === "frames" && "dropped" in msg) {
        setDropped(msg.dropped);
      }
      if (msg.type === "error" && "message" in msg) {
        setError(msg.message);
        setPending(false);
      }
    });
    return () => {
      // `catch` et non un simple `then` : hors de l'application empaquetée (essais, banc
      // de test), le pont vers le moteur n'existe pas et cette promesse peut ne jamais
      // aboutir. Une barre d'état ne doit jamais emporter le cockpit avec elle.
      unlisten.then((off) => off()).catch(() => {});
    };
  }, []);

  useEffect(() => {
    if (liveSince === null) {
      setElapsed(0);
      return;
    }
    const tick = () => setElapsed(Math.floor((Date.now() - liveSince) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [liveSince]);

  const live = liveSince !== null;

  async function toggle() {
    setError(null);
    setPending(true);
    try {
      await invoke(live ? "stop_stream" : "start_stream");
    } catch (cause: unknown) {
      // Le refus du contrôleur (moteur éteint) et celui du moteur (cible absente)
      // arrivent par deux chemins différents ; les deux doivent se lire au même endroit.
      setError(String(cause));
      setPending(false);
    }
  }

  return (
    <div className="flex flex-shrink-0 items-center gap-3 border-b border-hikari-line bg-hikari-bg-2 px-4 py-2">
      <button
        type="button"
        onClick={toggle}
        disabled={pending}
        className={`rounded-full px-4 py-1.5 text-[13px] font-semibold transition disabled:opacity-60
          focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-hikari-accent
          ${live ? "bg-hikari-live text-white hover:brightness-110" : "bg-hikari-accent text-[#1a1206] hover:brightness-110"}`}
      >
        {live ? "Arrêter" : "Démarrer"}
      </button>

      {live ? (
        <>
          <Badge tone="live">EN DIRECT</Badge>
          <span className="font-mono text-[13px] tabular-nums text-hikari-txt">
            {formatElapsed(elapsed)}
          </span>
        </>
      ) : null}

      {live && dropped !== null ? (
        <span className="text-[12.5px] text-hikari-txt-dim">
          {dropped} image{dropped > 1 ? "s" : ""} perdue{dropped > 1 ? "s" : ""}
        </span>
      ) : null}

      {error ? (
        <span role="alert" className="ml-auto text-[12.5px] text-hikari-red">
          {error}
        </span>
      ) : null}
    </div>
  );
}
