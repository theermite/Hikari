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
    Composition { width, height, fps: FPS_HAUT }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_compose_in_full_hd_on_a_full_hd_screen() {
        assert_eq!(
            composition(2560, 1440),
            Composition { width: 1920, height: 1080, fps: 60 }
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
        for (w, h) in [(3840, 2160), (2560, 1440), (1920, 1080), (1280, 720), (640, 480)] {
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
}
