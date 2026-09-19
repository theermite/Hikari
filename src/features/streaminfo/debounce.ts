// Un utilitaire minimal, PAS trouvé ailleurs dans le dépôt (recherché avant d'écrire,
// Quality.md « Lego Library ») — la recherche de catégorie (F-054) est le premier écran
// de Hikari à chercher à la frappe plutôt qu'à la validation.

/** Retarde l'appel de `fn` de `delayMs` après le dernier appel du retour — chaque appel
 * ANNULE le précédent minuteur plutôt que d'en cumuler plusieurs, sinon une frappe rapide
 * déclencherait une recherche par lettre tapée au lieu d'une seule, une fois la frappe
 * posée. */
export function debounce<Args extends unknown[]>(
  fn: (...args: Args) => void,
  delayMs: number,
): (...args: Args) => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  return (...args: Args) => {
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delayMs);
  };
}
