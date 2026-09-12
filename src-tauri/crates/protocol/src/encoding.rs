//! Choisir une définition, une cadence et un débit qui TIENNENT.
//!
//! Ce que ça règle (mesuré le 2026-09-07) : personne n'avait choisi ces trois valeurs. Le
//! débit était écrit en dur à 6000, la définition et la cadence étaient celles que le
//! moteur prend par défaut. Aucune ne venait de la machine de Jay ni de sa connexion — et
//! son premier direct long a perdu environ 2 % de ses images.
//!
//! Le principe qui gouverne tout ce module : **descendre vaut mieux que perdre**. Une
//! image jamais encodée ne se voit pas ; une image perdue se voit, et au pire moment. À
//! doute égal, on choisit le réglage le plus bas.
//!
//! DEUX décisions et non une, parce que le moteur les prend à deux moments différents :
//!   — la COMPOSITION (définition, cadence) se fixe au démarrage, avant que libobs
//!     n'existe. On ne sait alors rien des encodeurs, seulement la taille de l'écran ;
//!   — le DÉBIT se fixe au lancement d'une diffusion, quand libobs a dit quels encodeurs
//!     il sait faire tourner.
//!
//! Les mélanger obligerait à deviner l'encodeur au démarrage, et deviner ici veut dire
//! soit brider une machine capable, soit noyer une machine qui ne l'est pas.
//!
//! Les paliers viennent des recommandations publiques de Twitch. Ils sont volontairement
//! PEU nombreux : trois définitions et deux cadences couvrent tout le monde, et une
//! échelle continue donnerait l'illusion d'une précision que personne ne peut vérifier.

use serde::{Deserialize, Serialize};

/// La composition : ce que le moteur DESSINE, avant tout encodage.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Composition {
    pub width: u32,
    pub height: u32,
    pub fps: u32,
}

/// La cadence proposée. 60 partout où la définition le permet : en dessous, un jeu se voit
/// saccader, et c'est le premier reproche fait à un cockpit de stream.
const FPS_HAUT: u32 = 60;
/// La cadence de repli, quand la machine encode sans matériel dédié.
const FPS_BAS: u32 = 30;

/// Le plancher : sous cette taille, le texte d'un jeu devient illisible et la diffusion ne
/// sert plus à rien. Descendre encore serait une économie qui détruit l'objet.
const PLANCHER: (u32, u32) = (854, 480);

/// La composition pour un écran de cette taille.
///
/// Jamais plus grande que l'écran : agrandir une image ne crée aucun détail, seulement du
/// débit à transporter. Jamais plus petite que le plancher non plus.
pub fn composition(screen_width: u32, screen_height: u32) -> Composition {
    let (width, height) = if screen_width >= 1920 && screen_height >= 1080 {
        (1920, 1080)
    } else if screen_width >= 1280 && screen_height >= 720 {
        (1280, 720)
    } else {
        PLANCHER
    };
    Composition {
        width,
        height,
        fps: FPS_HAUT,
    }
}

/// Le débit, en kilobits par seconde, pour cette composition et cette machine.
///
/// C'est ici qu'intervient la question qui change tout : **cette machine encode-t-elle par
/// le matériel ?** Sans encodeur dédié, l'encodage prend le processeur — celui-là même qui
/// fait tourner le jeu. C'est la cause la plus fréquente d'images perdues sur une machine
/// par ailleurs confortable, et la raison de descendre.
///
/// Les valeurs viennent des recommandations publiques de Twitch, arrondies vers le BAS. Un
/// débit trop haut est refusé par la plateforme ou sature la connexion : dans les deux cas
/// l'image saccade, et rien à l'écran ne l'explique.
pub fn bitrate_kbps(composition: Composition, hardware_encoder: bool) -> u32 {
    let plein = match (composition.height, composition.fps) {
        (h, 60) if h >= 1080 => 6000,
        (h, _) if h >= 1080 => 4500,
        (h, 60) if h >= 720 => 4500,
        (h, _) if h >= 720 => 3000,
        (_, 60) => 2500,
        _ => 1500,
    };
    if hardware_encoder {
        return plein;
    }
    // Sans matériel, le processeur fait deux métiers à la fois. Les deux tiers laissent de
    // la marge au jeu, et une image un peu moins fine vaut mieux qu'une image qui saute.
    (plein * 2 / 3).max(1500)
}

/// La cadence à composer quand on sait déjà que la machine encode sans matériel.
///
/// Rendue à part parce que le moteur ne le sait PAS au démarrage : elle sert au jour où
/// l'utilisateur choisira son réglage dans l'écran Paramètres, et à ce moment-là seulement.
pub fn fps_without_hardware() -> u32 {
    FPS_BAS
}

/// Ce jour est arrivé (B-settings, 2026-09-12) : l'utilisateur choisit lui-même sa
/// composition, son encodeur et son débit — parce que le calcul ci-dessus, fondé
/// uniquement sur la taille de l'écran, a produit ~65 % de pertes d'images sur une
/// machine dont la CONNEXION ne suivait pas (Jay, notes de session).
///
/// L'encodeur — nommé par l'utilisateur, distinct du type libobs (`ObsVideoEncoderType`)
/// que seul le crate `engine`, lié à libobs, peut même compiler contre (ADR-013).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EncoderChoice {
    Nvenc,
    X264,
}

/// Résout la résolution/cadence réellement encodée et envoyée : le réglage choisi à la
/// main (B-settings) s'il existe, sinon le canevas de base.
///
/// Le canevas — là où les sources sont posées (position, taille) — ne passe JAMAIS par
/// cette fonction. C'est la séparation que fait déjà libobs lui-même
/// (`base_width/height` contre `output_width/height`) : notre bug du zoom d'aperçu
/// (2026-09-12) venait justement de fixer les deux au même réglage choisi à la main.
pub fn resolve_output(base: Composition, override_: Option<Composition>) -> Composition {
    override_.unwrap_or(base)
}

/// Parse une composition choisie à la main, au format `"<largeur>x<hauteur>@<cadence>"`
/// (ex. `"1920x1080@60"`) — LA MÊME forme que les paliers ci-dessus, jamais trois champs
/// indépendants. Une composition à moitié posée n'est pas un pari plus sûr qu'aucune :
/// c'est une supposition qui porte l'autorité des deux autres valeurs.
///
/// `None` sur tout ce qui ne colle pas au format, y compris l'absence de réglage — c'est
/// l'appelant impur (lecture d'une variable d'environnement) qui décide alors de retomber
/// sur `composition()` ci-dessus.
pub fn composition_override(value: Option<&str>) -> Option<Composition> {
    let (size, fps) = value?.split_once('@')?;
    let (width, height) = size.split_once('x')?;
    let width: u32 = width.parse().ok().filter(|w| *w > 0)?;
    let height: u32 = height.parse().ok().filter(|h| *h > 0)?;
    let fps: u32 = fps.parse().ok().filter(|f| *f > 0)?;
    Some(Composition { width, height, fps })
}

/// Parse un débit choisi à la main, en kbit/s. `None` sur l'absence de réglage ou une
/// valeur qui ne peut pas correspondre à un débit réel (zéro, négatif, illisible).
pub fn bitrate_override(value: Option<&str>) -> Option<u32> {
    value?.parse::<u32>().ok().filter(|b| *b > 0)
}

/// Parse un encodeur choisi à la main. Insensible à la casse. `None` sur l'absence de
/// réglage ou un nom que ce module ne reconnaît pas — jamais une famille d'encodeur
/// inventée : l'appelant retombe alors sur la détection réelle (F-003, `preflight.rs`).
pub fn encoder_override(value: Option<&str>) -> Option<EncoderChoice> {
    match value?.to_lowercase().as_str() {
        "nvenc" => Some(EncoderChoice::Nvenc),
        "x264" => Some(EncoderChoice::X264),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_compose_in_full_hd_on_a_full_hd_screen() {
        assert_eq!(
            composition(2560, 1440),
            Composition {
                width: 1920,
                height: 1080,
                fps: 60
            }
        );
    }

    #[test]
    fn should_never_compose_larger_than_the_screen() {
        // Agrandir une image ne cree aucun detail, seulement du debit a transporter.
        let choisi = composition(1280, 720);

        assert_eq!((choisi.width, choisi.height), (1280, 720));
    }

    #[test]
    fn should_keep_a_floor_where_text_stays_readable() {
        assert_eq!(
            (composition(800, 600).width, composition(800, 600).height),
            PLANCHER
        );
    }

    #[test]
    fn should_survive_a_screen_that_reports_nothing() {
        // Un ecran a 0x0 arrive : un affichage debranche, un pilote qui ne repond pas. Un
        // reglage a zero ferait echouer le demarrage sans rien expliquer.
        let choisi = composition(0, 0);

        assert!(choisi.width >= PLANCHER.0 && choisi.height >= PLANCHER.1);
        assert!(choisi.fps >= 30);
    }

    #[test]
    fn should_use_the_full_bitrate_with_a_hardware_encoder() {
        assert_eq!(bitrate_kbps(composition(1920, 1080), true), 6000);
    }

    #[test]
    fn should_lower_the_bitrate_without_a_hardware_encoder() {
        // Le processeur fait alors deux metiers a la fois. Une image un peu moins fine
        // vaut mieux qu'une image qui saute.
        let avec = bitrate_kbps(composition(1920, 1080), true);
        let sans = bitrate_kbps(composition(1920, 1080), false);

        assert!(sans < avec, "sans={sans} avec={avec}");
    }

    #[test]
    fn should_never_propose_a_bitrate_twitch_refuses() {
        // 6000 kbit/s est le plafond public pour un compte ordinaire. Au-dela, la
        // plateforme refuse ou coupe — et l'image saccade sans que personne ne sache
        // pourquoi.
        for (w, h) in [
            (3840, 2160),
            (2560, 1440),
            (1920, 1080),
            (1280, 720),
            (640, 480),
        ] {
            for materiel in [true, false] {
                let debit = bitrate_kbps(composition(w, h), materiel);
                assert!(debit <= 6000, "{w}x{h} materiel={materiel} -> {debit}");
                assert!(debit >= 1500, "{w}x{h} materiel={materiel} -> {debit}");
            }
        }
    }

    #[test]
    fn should_scale_the_bitrate_with_the_resolution() {
        let grand = bitrate_kbps(composition(1920, 1080), true);
        let petit = bitrate_kbps(composition(800, 600), true);

        assert!(petit < grand, "petit={petit} grand={grand}");
    }

    #[test]
    fn should_resolve_output_to_the_base_canvas_when_no_override() {
        let base = composition(1920, 1080);

        assert_eq!(resolve_output(base, None), base);
    }

    #[test]
    fn should_resolve_output_to_the_override_leaving_the_base_untouched() {
        let base = composition(1920, 1080);
        let choisi = Composition {
            width: 1280,
            height: 720,
            fps: 30,
        };

        assert_eq!(resolve_output(base, Some(choisi)), choisi);
        // La fonction ne modifie jamais son argument `base` — c'est l'appelant qui garde
        // le canevas séparé (voir engine::main::composition() contre output_composition()).
        assert_eq!(base, composition(1920, 1080));
    }

    #[test]
    fn should_parse_a_composition_override() {
        assert_eq!(
            composition_override(Some("1920x1080@60")),
            Some(Composition {
                width: 1920,
                height: 1080,
                fps: 60
            })
        );
    }

    #[test]
    fn should_reject_a_composition_override_that_is_auto_or_absent() {
        assert_eq!(composition_override(Some("auto")), None);
        assert_eq!(composition_override(None), None);
    }

    #[test]
    fn should_reject_a_composition_override_missing_the_cadence() {
        // Sans le "@60" : un format à moitié posé n'est pas un pari plus sûr qu'aucun.
        assert_eq!(composition_override(Some("1920x1080")), None);
    }

    #[test]
    fn should_reject_a_composition_override_with_a_zero_component() {
        assert_eq!(composition_override(Some("0x1080@60")), None);
        assert_eq!(composition_override(Some("1920x0@60")), None);
        assert_eq!(composition_override(Some("1920x1080@0")), None);
    }

    #[test]
    fn should_reject_an_unreadable_composition_override() {
        assert_eq!(composition_override(Some("plein-ecran")), None);
    }

    #[test]
    fn should_parse_a_bitrate_override() {
        assert_eq!(bitrate_override(Some("4500")), Some(4500));
    }

    #[test]
    fn should_reject_a_bitrate_override_that_is_auto_absent_or_zero() {
        assert_eq!(bitrate_override(Some("auto")), None);
        assert_eq!(bitrate_override(None), None);
        assert_eq!(bitrate_override(Some("0")), None);
        assert_eq!(bitrate_override(Some("-100")), None);
    }

    #[test]
    fn should_parse_an_encoder_override_case_insensitively() {
        assert_eq!(encoder_override(Some("nvenc")), Some(EncoderChoice::Nvenc));
        assert_eq!(encoder_override(Some("NVENC")), Some(EncoderChoice::Nvenc));
        assert_eq!(encoder_override(Some("x264")), Some(EncoderChoice::X264));
    }

    #[test]
    fn should_reject_an_encoder_override_that_is_auto_absent_or_unrecognized() {
        assert_eq!(encoder_override(Some("auto")), None);
        assert_eq!(encoder_override(None), None);
        // QSV existe chez libobs mais ce module ne le reconnaît pas comme sûr
        // (`preflight.rs`) : jamais inventer une famille d'encodeur non détectée.
        assert_eq!(encoder_override(Some("qsv")), None);
    }
}
