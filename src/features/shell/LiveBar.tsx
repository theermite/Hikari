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
import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "../../components/ui/Badge";
import { ComingSoon } from "../../components/ui/ComingSoon";
import { runPreflight } from "../preflight/api";
import { applyProposedComposition } from "../preflight/applyProposal";
import type { PreflightOutcome } from "../preflight/types";
import { type DropVerdict, dropRate, dropVerdict } from "./frames";

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

/** La couleur dit l'URGENCE, le titre dit QUOI FAIRE. Une couleur seule laisse deviner ;
 * un rouge sans explication fait chercher la panne au mauvais endroit — ces images sont
 * perdues par le RÉSEAU, jamais par la machine ni par l'encodage. */
const COULEUR_VERDICT: Record<DropVerdict, string> = {
  ok: "text-hikari-green",
  attention: "text-hikari-accent",
  critique: "text-hikari-red",
};

const TITRE_VERDICT: Record<DropVerdict, string> = {
  ok: "Ta connexion suit le débit d'envoi.",
  attention:
    "Ta connexion commence à peiner — surveille avant que ça se voie à l'écran.",
  critique:
    "Ta connexion ne suit plus : tes spectateurs voient des saccades. Baisse le débit d'envoi.",
};

/** Une décimale, virgule française. Au-delà, la précision n'aide personne à décider. */
function formatTaux(taux: number): string {
  return `(${taux.toFixed(1).replace(".", ",")} %)`;
}

export function LiveBar() {
  const [liveSince, setLiveSince] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [dropped, setDropped] = useState<number | null>(null);
  // Le moteur envoyait déjà le total ; seul le nombre perdu était retenu. Sans lui, pas de
  // taux — et le seuil de Jay est un taux (2 %), pas un compte.
  const [totalFrames, setTotalFrames] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  // Le pré-vol informe, il ne bloque jamais (Jay, 2026-09-13 : « laisser le choix à
  // l'utilisateur, au moins il était au courant du risque » — plutôt qu'un mur, une
  // bannière avec le risque réel et un réglage plus prudent suggéré).
  const [checking, setChecking] = useState(false);
  const [preflightWarning, setPreflightWarning] =
    useState<PreflightOutcome | null>(null);
  const [applied, setApplied] = useState(false);
  /** Une référence et non l'état : l'écoute du moteur est posée une seule fois et
   * garderait sinon la valeur du premier rendu, c'est-à-dire `false` pour toujours. */
  const pendingRef = useRef(false);

  // `useCallback` sans dépendance : la fonction ne touche que la référence et le poseur
  // d'état, tous deux stables. Sans cela elle serait recréée à chaque rendu, et l'écoute
  // du moteur — qui s'en sert — devrait se réabonner sans arrêt, ou mentir sur ce dont
  // elle dépend.
  const askEngine = useCallback((next: boolean) => {
    pendingRef.current = next;
    setPending(next);
  }, []);

  useEffect(() => {
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "started") {
        setLiveSince(Date.now());
        setDropped(null);
        setTotalFrames(0);
        setError(null);
        askEngine(false);
      }
      if (msg.type === "stream_stopped") {
        setLiveSince(null);
        askEngine(false);
      }
      if (msg.type === "frames" && "dropped" in msg) {
        setDropped(msg.dropped);
        setTotalFrames(msg.total ?? 0);
      }
      // Seulement quand CETTE barre attend une réponse. Le moteur émet toutes ses
      // erreurs sur un canal unique : sans ce filtre, la barre du direct affiche les
      // erreurs de scène des autres panneaux. Vécu 2026-09-05 — « Monitor Capture
      // existe déjà dans cette scène » trônait à côté du bouton Démarrer.
      if (msg.type === "error" && "message" in msg && pendingRef.current) {
        setError(msg.message);
        askEngine(false);
      }
    });
    return () => {
      // `catch` et non un simple `then` : hors de l'application empaquetée (essais, banc
      // de test), le pont vers le moteur n'existe pas et cette promesse peut ne jamais
      // aboutir. Une barre d'état ne doit jamais emporter le cockpit avec elle.
      unlisten.then((off) => off()).catch(() => {});
    };
  }, [askEngine]);

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

  async function startNow() {
    askEngine(true);
    try {
      await invoke("start_stream");
    } catch (cause: unknown) {
      // Le refus du contrôleur (moteur éteint) et celui du moteur (cible absente)
      // arrivent par deux chemins différents ; les deux doivent se lire au même endroit.
      setError(String(cause));
      askEngine(false);
    }
  }

  async function toggle() {
    if (live) {
      setError(null);
      askEngine(true);
      try {
        await invoke("stop_stream");
      } catch (cause: unknown) {
        setError(String(cause));
        askEngine(false);
      }
      return;
    }

    // Le pré-vol tourne AVANT chaque démarrage — une mesure réseau réelle prend quelques
    // secondes, le bouton le dit ("Vérification…"). Jamais un mur : `outcome.ok` faux
    // ouvre une bannière informée, jamais un blocage silencieux du bouton.
    setError(null);
    setPreflightWarning(null);
    setApplied(false);
    setChecking(true);
    try {
      const outcome = await runPreflight();
      setChecking(false);
      if (outcome.ok) {
        await startNow();
      } else {
        setPreflightWarning(outcome);
      }
    } catch (cause: unknown) {
      setChecking(false);
      setError(String(cause));
    }
  }

  async function startAnyway() {
    setPreflightWarning(null);
    await startNow();
  }

  async function applyForNextTime(composition: {
    width: number;
    height: number;
    fps: number;
  }) {
    // Écrit le réglage, jamais le direct en cours : le moteur ne relit ses réglages
    // d'encodage qu'à SON propre démarrage (ADR-013, `encoding_settings.rs`), déjà en
    // route au moment où "Démarrer" devient cliquable (l'Aperçu l'a lancé). L'appliquer
    // ici ne changerait rien à ce direct — un bouton "et diffuser" l'aurait pourtant
    // laissé croire (relecture indépendante, 2026-09-13). On informe, sans mentir sur
    // l'effet : le réglage tiendra au prochain lancement du moteur.
    await applyProposedComposition(composition);
    setApplied(true);
  }

  // Calculés à chaque rendu et non stockés : ce sont des fonctions de `dropped` et
  // `totalFrames`, et un état dérivé qu'on range finit par mentir sur son origine.
  const taux = dropRate(dropped ?? 0, totalFrames);
  const verdict = dropVerdict(taux);

  return (
    <div className="flex flex-shrink-0 items-center gap-3 border-b border-hikari-line px-4 py-2.5">
      {/* Le sélecteur de préréglage de la maquette (« LoL du soir ») : un préréglage
          réunit des plateformes, une collection de scènes et un titre de direct. Aucun de
          ces trois concepts n'existe encore côté moteur. */}
      <ComingSoon what="choisir un préréglage de direct (plateformes, scènes, titre)">
        <span className="flex items-center gap-1.5 rounded-full border border-hikari-line px-3 py-1.5 text-[12.5px] text-hikari-txt-dim">
          Préréglage <span className="font-medium text-hikari-txt">—</span> ▾
        </span>
      </ComingSoon>

      <button
        type="button"
        onClick={toggle}
        disabled={pending || checking}
        className={`rounded-full px-4 py-1.5 text-[13px] font-semibold transition disabled:opacity-60
          focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-hikari-accent
          ${live ? "bg-hikari-live text-white hover:brightness-110" : "bg-hikari-accent text-[#1a1206] hover:brightness-110"}`}
      >
        {checking ? "Vérification…" : live ? "Arrêter" : "Démarrer"}
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
          {taux !== null ? (
            <>
              {" "}
              <span
                data-testid="taux-images-perdues"
                className={COULEUR_VERDICT[verdict ?? "ok"]}
                title={TITRE_VERDICT[verdict ?? "ok"]}
              >
                {formatTaux(taux)}
              </span>
            </>
          ) : null}
        </span>
      ) : null}

      {/* La case des spectateurs est TOUJOURS là, même sans valeur (Jay, 2026-09-05 :
          « de cette manière je le vois tout de même et je sais où il est »). Elle affiche
          « n/a », jamais un zéro : montrer la case renseigne, inventer un chiffre ment.
          Le titre au survol dit ce qui la remplirait, pour qu'une valeur morte ne soit
          pas une impasse. Elle se remplira quand les plateformes seront branchées. */}
      <span
        className="text-[12.5px] text-hikari-txt-dim"
        title="Aucun compte connecté — le nombre de spectateurs arrivera avec Twitch ou YouTube"
      >
        Spectateurs <span className="text-hikari-txt-faint">n/a</span>
      </span>

      {/* Les emplacements que la maquette prévoit et que rien n'alimente encore. Dessinés
          et marqués, jamais absents : Jay veut voir ce qui arrive et garder un squelette
          cohérent (2026-09-05). Ils s'allumeront quand leur brique existera. */}
      <ComingSoon what="le débit réel de la diffusion">
        <span className="text-[12.5px] text-hikari-txt-dim">— Mb/s</span>
      </ComingSoon>
      <ComingSoon what="couper les alertes pendant un moment délicat">
        <span className="rounded-full border border-hikari-line px-2.5 py-1 text-[12.5px] text-hikari-txt-dim">
          🔔 Silence alertes
        </span>
      </ComingSoon>

      {error ? (
        <span role="alert" className="ml-auto text-[12.5px] text-hikari-red">
          {error}
        </span>
      ) : null}

      {preflightWarning
        ? (() => {
            const proposed = preflightWarning.proposed_composition;
            return (
              <div
                role="alert"
                className="ml-auto flex items-center gap-2 rounded-[10px] border border-hikari-accent px-3 py-1.5 text-[12.5px]"
              >
                <span className="text-hikari-txt">
                  ⚠️ {preflightWarning.reason}
                </span>
                {proposed ? (
                  <span className="text-hikari-txt-dim">
                    Réglage suggéré : {proposed.width}×{proposed.height}{" "}
                    {proposed.fps} i/s.{" "}
                    {applied ? (
                      "Appliqué — tiendra au prochain lancement du moteur."
                    ) : (
                      <button
                        type="button"
                        onClick={() => applyForNextTime(proposed)}
                        className="underline hover:text-hikari-txt"
                      >
                        Appliquer pour le prochain lancement
                      </button>
                    )}
                  </span>
                ) : null}
                <button
                  type="button"
                  onClick={startAnyway}
                  className="underline text-hikari-txt-dim hover:text-hikari-txt"
                >
                  Diffuser quand même
                </button>
                <button
                  type="button"
                  onClick={() => setPreflightWarning(null)}
                  className="text-hikari-txt-faint hover:text-hikari-txt-dim"
                >
                  Annuler
                </button>
              </div>
            );
          })()
        : null}
    </div>
  );
}
