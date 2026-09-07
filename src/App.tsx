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

function App() {
  return (
    <MorphicProvider>
      <Cockpit />
    </MorphicProvider>
  );
}

export default App;
