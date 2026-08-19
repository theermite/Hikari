// Déclare les matchers de @testing-library/jest-dom (toBeInTheDocument, toHaveAttribute...)
// pour le contrôle de types. `vitest.setup.ts`, à la racine, est hors du périmètre inclus
// par tsconfig.json (`include: ["src"]`) — sa propre référence triple-slash n'atteint donc
// jamais les fichiers de test. Ce fichier vit dans `src` pour cette seule raison.
/// <reference types="@testing-library/jest-dom" />
