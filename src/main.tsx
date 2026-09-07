import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
// Les deux feuilles du module d'adaptation, avant la nôtre : la première pose ses
// variables de base, la seconde habille son bouton. Chargées ici et pas dans le composant
// — une feuille importée depuis un composant se charge à son premier affichage, donc après
// le premier rendu, et l'écran clignote.
import "@theermite/morphic-adapter/morphic.css";
import "@theermite/morphic-adapter/ui.css";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
