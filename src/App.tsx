// Hikari — point d'entrée applicatif. La coque plate de B0.3 est remplacée par le vrai
// cockpit à panneaux (B-shell). Zéro logique métier ici : App monte le fournisseur
// d'adaptation morphique, puis le Cockpit qui héberge tous les écrans.
//
// Le fournisseur est ICI et pas plus bas : il porte les préférences de confort — thème,
// mouvement, contraste, densité, police — et elles concernent TOUTE la fenêtre, y compris
// la barre de titre et la barre latérale. Posé à l'intérieur du cockpit, il aurait laissé
// dehors les deux endroits que l'utilisateur regarde en premier.

import { MorphicProvider } from "@theermite/morphic-adapter";
import { Cockpit } from "./features/shell/Cockpit";
import {
  readSettingsWindowParams,
  SettingsWindow,
} from "./features/shell/SettingsWindow";

// Une fenêtre de réglages (Jay, 2026-09-07 : « une fenêtre qui apparaît pour que l'on
// puisse régler », comme dans OBS) partage le même point d'entrée que la fenêtre
// principale — c'est le même exécutable, le même index.html — et se distingue par les
// paramètres que `open_settings_window` pose dans son URL. Lu UNE fois, au montage : ces
// paramètres ne changent jamais pour la durée de vie de cette fenêtre précise.
//
// `typeof window` et non un accès direct : ce composant passe aussi par un rendu SERVEUR
// dans ses propres tests de coque (`renderToStaticMarkup`), où `window` n'existe pas.
const settingsParams =
  typeof window === "undefined"
    ? null
    : readSettingsWindowParams(window.location.search);

function App() {
  return (
    <MorphicProvider>
      {settingsParams ? <SettingsWindow {...settingsParams} /> : <Cockpit />}
    </MorphicProvider>
  );
}

export default App;
