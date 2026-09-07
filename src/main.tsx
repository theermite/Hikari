import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
// Les deux feuilles du module d'adaptation, avant la nôtre : la première pose ses
// variables de base, la seconde habille son bouton. Chargées ici et pas dans le composant
// — une feuille importée depuis un composant se charge à son premier affichage, donc après
// le premier rendu, et l'écran clignote.
import "@theermite/morphic-adapter/morphic.css";
import "@theermite/morphic-adapter/ui.css";
// Les deux polices d'accessibilité, EMBARQUÉES et non seulement nommées.
//
// Jay, 2026-09-07 : « es-tu sûr qu'Atkinson et OpenDyslexic sont bien les polices qui
// s'affichent ? » Elles ne l'étaient pas. Les noms figuraient dans notre feuille de style,
// les fichiers nulle part, et Windows n'en installe aucune des deux : choisir « Atkinson »
// donnait Verdana, « OpenDyslexic » donnait Comic Sans. Une option d'accessibilité qui
// livre autre chose que ce qu'elle annonce est pire qu'une option absente.
//
// Deux graisses seulement (normale et grasse) : ce sont celles que l'interface utilise, et
// embarquer les italiques alourdirait l'installeur pour rien.
//
// Licence OFL-1.1 pour les deux, vérifiée le 2026-09-07 — compatible avec un dépôt public
// sous GPL-3.0, et l'embarquement est explicitement autorisé par cette licence.
import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "@fontsource/opendyslexic/400.css";
import "@fontsource/opendyslexic/700.css";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
