// Panneau Aperçu (B1 dette payée) — le moteur démarre à l'ouverture de ce panneau et
// s'arrête à sa fermeture (jamais 100% du temps, décision Jay 2026-07-22 : le moteur tient
// des ressources GPU/capture). L'image réelle est greffée dans le rectangle exact de CE
// panneau (option B, Jay 2026-07-23) — jamais toute la fenêtre app. Ce composant mesure
// sa propre zone (position + taille réelles à l'écran) et la transmet à chaque
// changement ; masque la fenêtre native quand son onglet devient inactif (sinon elle
// resterait visible par-dessus l'onglet affiché).

import { listen } from "@tauri-apps/api/event";
import type { IDockviewPanelProps } from "dockview-react";
import { useEffect, useRef, useState } from "react";
import { hidePreview, positionPreview, startEngine, stopEngine } from "./api";
import type { EngineMessage } from "./types";

type State =
  | { status: "starting" }
  | { status: "ready" }
  | { status: "scene"; sources: string[] }
  | { status: "error"; message: string }
  | { status: "stopped" };

export function PreviewPanel(props: IDockviewPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<State>({ status: "starting" });

  useEffect(() => {
    const unlisten = listen<EngineMessage>("engine-message", (event) => {
      const msg = event.payload;
      if (msg.type === "ready") {
        setState({ status: "ready" });
      } else if (msg.type === "sources" && msg.items) {
        setState({
          status: "scene",
          sources: msg.items.map((item) => item.name),
        });
      } else if (msg.type === "error" && msg.message) {
        setState({ status: "error", message: msg.message });
      } else if (msg.type === "stopped") {
        setState({ status: "stopped" });
      }
    });

    startEngine().catch((error: unknown) => {
      setState({ status: "error", message: String(error) });
    });

    return () => {
      unlisten.then((f) => f());
      stopEngine().catch((error: unknown) => {
        console.error("preview: stop_engine failed", error);
      });
    };
  }, []);

  useEffect(() => {
    const reportRect = () => {
      if (!props.api.isVisible) {
        hidePreview().catch((error: unknown) => {
          console.error("preview: hide_preview failed", error);
        });
        return;
      }
      const el = containerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      positionPreview(
        Math.round(rect.x),
        Math.round(rect.y),
        Math.round(rect.width),
        Math.round(rect.height),
      ).catch((error: unknown) => {
        console.error("preview: position_preview failed", error);
      });
    };

    reportRect();

    // Three independent triggers: the panel's OWN size (dimensions), its tab visibility
    // (active/inactive), and the whole dock's layout (a SIBLING panel resizing can shift
    // this one's position without changing ITS OWN dimensions — dimensions alone misses
    // that case).
    const dims = props.api.onDidDimensionsChange(reportRect);
    const visibility = props.api.onDidVisibilityChange(reportRect);
    const active = props.api.onDidActiveChange(reportRect);
    const layout = props.containerApi.onDidLayoutChange(reportRect);

    const resizeObserver = new ResizeObserver(reportRect);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      dims.dispose();
      visibility.dispose();
      active.dispose();
      layout.dispose();
      resizeObserver.disconnect();
    };
  }, [props.api, props.containerApi]);

  return (
    <div ref={containerRef} className="h-full w-full bg-hikari-bg-3">
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center text-hikari-txt">
        {state.status === "starting" && (
          <p className="text-hikari-txt-faint">Démarrage du moteur…</p>
        )}
        {state.status === "ready" && (
          <p className="text-hikari-txt-faint">
            Moteur prêt — en attente de la scène.
          </p>
        )}
        {state.status === "scene" && (
          <p className="text-hikari-green">
            ✅ Scène active : {state.sources.join(", ")}
          </p>
        )}
        {state.status === "error" && (
          <p className="text-hikari-red">❌ {state.message}</p>
        )}
        {state.status === "stopped" && (
          <p className="text-hikari-txt-faint">Moteur arrêté.</p>
        )}
      </div>
    </div>
  );
}
