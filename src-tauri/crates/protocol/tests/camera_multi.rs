//! Plusieurs caméras à la fois (2026-09-06) — contrat de nommage et de fil.
//!
//! Jusqu'ici Hikari n'avait qu'UNE caméra, nommée « Webcam ». Choisir un deuxième appareil
//! ne créait rien : le moteur renvoyait le premier ouvert, sans erreur, et l'utilisateur
//! voyait la mauvaise image. Le modèle « une caméra physique » vivait dans le protocole
//! autant que dans le moteur, donc il se corrige ici d'abord.
//!
//! Deux choses se prouvent sans libobs, et sont donc testées : le NOM que reçoit chaque
//! caméra (il doit rester unique, sinon deux sources se confondent côté moteur), et le
//! fait que chaque commande caméra désigne DE QUELLE caméra elle parle.

use hikari_protocol::{
    camera_source_name, parse_controller_command, parse_engine_message, to_line, ControllerCommand,
    EngineMessage, CAMERA_SOURCE_NAME,
};
use proptest::prelude::*;

#[test]
fn should_name_a_camera_after_the_device_the_user_picked() {
    assert_eq!(
        camera_source_name("Logitech StreamCam", &[]),
        "Logitech StreamCam"
    );
}

/// Deux exemplaires du même modèle rapportent le MÊME nom d'appareil. Sans départage, la
/// deuxième source écraserait la première côté libobs, où le nom est la clé.
#[test]
fn should_keep_the_name_unique_when_two_devices_share_a_label() {
    let taken = vec!["Logitech StreamCam".to_string()];
    assert_eq!(
        camera_source_name("Logitech StreamCam", &taken),
        "Logitech StreamCam (2)"
    );
}

#[test]
fn should_keep_counting_when_the_suffixed_name_is_taken_too() {
    let taken = vec!["Webcam".to_string(), "Webcam (2)".to_string()];
    assert_eq!(camera_source_name("Webcam", &taken), "Webcam (3)");
}

/// Un appareil sans nom exploitable retombe sur le nom historique plutôt que de produire
/// une source anonyme, impossible à désigner dans l'interface.
#[test]
fn should_fall_back_to_the_historic_name_when_the_device_has_none() {
    assert_eq!(camera_source_name("   ", &[]), CAMERA_SOURCE_NAME);
}

#[test]
fn should_say_which_camera_a_removal_targets() {
    let cmd = ControllerCommand::RemoveCamera {
        device_id: "usb#vid_046d".to_string(),
        scene: "Jeu".to_string(),
    };
    let line = to_line(&cmd).expect("serializes");
    assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
}

#[test]
fn should_say_which_camera_a_filter_toggle_targets() {
    let cmd = ControllerCommand::SetCircleMask {
        device_id: "usb#vid_046d".to_string(),
        scene: "Jeu".to_string(),
        enabled: true,
    };
    let line = to_line(&cmd).expect("serializes");
    assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
}

#[test]
fn should_say_which_camera_a_transform_reports_on() {
    let msg = EngineMessage::CameraTransform {
        device_id: "usb#vid_046d".to_string(),
        scene: "Jeu".to_string(),
        x: 10,
        y: 20,
        scale_percent: 100,
    };
    let line = to_line(&msg).expect("serializes");
    assert_eq!(parse_engine_message(&line).expect("parses"), msg);
}

proptest! {
    /// La propriété qui compte vraiment : quel que soit le nom rapporté par l'appareil, le
    /// nom retenu n'entre jamais en collision avec un nom déjà pris. C'est cette unicité,
    /// et non un cas d'exemple, qui empêche deux caméras de se confondre.
    #[test]
    fn should_never_collide_with_a_name_already_taken(
        device_name in any::<String>(),
        taken in prop::collection::vec(any::<String>(), 0..8),
    ) {
        let chosen = camera_source_name(&device_name, &taken);
        prop_assert!(!taken.contains(&chosen));
        prop_assert!(!chosen.trim().is_empty());
    }
}
