// Hikari — point d'entrée applicatif. La coque plate de B0.3 est remplacée par le vrai
// cockpit à panneaux (B-shell). Zéro logique métier ici : App ne fait que monter le
// Cockpit, qui héberge tous les écrans (PET fiche B-shell).

import { Cockpit } from "./features/shell/Cockpit";

function App() {
  return <Cockpit />;
}

export default App;
