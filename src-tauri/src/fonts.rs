//! Détection des polices installées sur la machine (session nocturne 2026-09-09).
//!
//! POURQUOI : le panneau de réglages de texte proposait sept polices écrites en dur, dont
//! deux — Atkinson Hyperlegible, OpenDyslexic — ne sont EMBARQUÉES nulle part pour le
//! moteur (aucun fichier `.ttf`/`.otf` dans le dépôt) : elles ne sont chargées que comme
//! polices WEB pour l'écran d'adaptation morphique, un système entièrement différent de la
//! source texte du moteur, qui dessine avec les polices que WINDOWS connaît. Les nommer
//! sans qu'elles soient installées est la même fausse promesse que Jay a attrapée le
//! 2026-09-07 sur le panneau d'adaptation. Ce module remplace la supposition par une
//! lecture réelle du système, via l'API Windows faite pour ça.

use windows::Win32::Foundation::LPARAM;
use windows::Win32::Graphics::Gdi::{
    EnumFontFamiliesExW, GetDC, ReleaseDC, DEFAULT_CHARSET, LOGFONTW, TEXTMETRICW,
};

/// Lit le nom de police dans `lfFaceName` (UTF-16, terminé par zéro ou plein).
fn face_name(logfont: &LOGFONTW) -> String {
    let fin = logfont
        .lfFaceName
        .iter()
        .position(|&c| c == 0)
        .unwrap_or(logfont.lfFaceName.len());
    String::from_utf16_lossy(&logfont.lfFaceName[..fin])
}

/// Callback appelé par Windows une fois par police trouvée. `lparam` porte le pointeur vers
/// le `Vec` qui collecte les noms — c'est le contrat de cette API, jamais une variable
/// globale.
unsafe extern "system" fn collect(
    logfont: *const LOGFONTW,
    _metrics: *const TEXTMETRICW,
    _kind: u32,
    lparam: LPARAM,
) -> i32 {
    // Safety: Windows garantit `logfont` valide pendant la durée de cet appel, et `lparam`
    // porte le pointeur que `list_installed_fonts` vient de construire, vivant pour toute
    // l'énumération — synchrone, donc jamais utilisé après son retour.
    unsafe {
        let noms = &mut *(lparam.0 as *mut Vec<String>);
        noms.push(face_name(&*logfont));
    }
    1 // continue l'énumération — 0 l'arrêterait
}

/// Les polices réellement installées sur cette machine, triées, sans doublon.
///
/// `DEFAULT_CHARSET` avec un nom de police vide énumère TOUTES les polices, une fois par
/// jeu de caractères qu'elles supportent — d'où le doublon à filtrer : une police portant
/// à la fois le latin et le cyrillique apparaît deux fois sous le même nom.
pub fn list_installed_fonts() -> Vec<String> {
    let logfont = LOGFONTW {
        lfCharSet: DEFAULT_CHARSET,
        ..Default::default()
    };

    let mut noms: Vec<String> = Vec::new();
    // Safety: `GetDC(None)` rend le contexte de l'écran, valide pour la durée de cet appel
    // synchrone, et relâché juste après comme l'API l'exige. `noms` vit jusqu'à la fin de
    // cette fonction, donc au-delà du retour de `EnumFontFamiliesExW`, qui est bloquant.
    unsafe {
        let hdc = GetDC(None);
        let _ = EnumFontFamiliesExW(
            hdc,
            &logfont,
            Some(collect),
            LPARAM(std::ptr::addr_of_mut!(noms) as isize),
            0,
        );
        let _ = ReleaseDC(None, hdc);
    }

    noms.sort();
    noms.dedup();
    noms
}

/// La liste des polices installées, pour le sélecteur de police d'une source texte.
#[tauri::command]
pub(crate) fn list_fonts() -> Vec<String> {
    list_installed_fonts()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Preuve réelle, pas un bouchon : la machine de développement porte toujours au moins
    /// les polices système de Windows (Arial, Segoe UI...). Une liste vide signalerait un
    /// appel cassé, jamais une machine sans police.
    #[test]
    fn should_list_real_fonts_sorted_and_deduplicated() {
        let fonts = list_installed_fonts();

        assert!(!fonts.is_empty(), "aucune police détectée sur la machine");

        let mut triees = fonts.clone();
        triees.sort();
        assert_eq!(fonts, triees, "la liste n'est pas triée");

        let mut uniques = fonts.clone();
        uniques.dedup();
        assert_eq!(fonts, uniques, "la liste contient des doublons");

        // Arial est une police système Windows depuis toujours — sa présence prouve que
        // l'énumération a vraiment parcouru le système, pas un sous-ensemble vide.
        assert!(
            fonts.iter().any(|f| f == "Arial"),
            "Arial absente — l'énumération n'a rien lu"
        );
    }
}
