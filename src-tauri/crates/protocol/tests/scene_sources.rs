//! Sources de scène (brique Sources, tranche 1) — contrat pur : identifiants libobs exacts,
//! validation du nom, aller-retour du fil. La création réelle des sources est du régime
//! intégration, prouvée en lançant l'app.

use hikari_protocol::{
    CaptureKind, CaptureTarget, ControllerCommand, EngineMessage, SceneInfo, SceneNameError,
    SceneSourceInfo, parse_controller_command, parse_engine_message, to_line, validate_source_name,
};
use proptest::prelude::*;

#[test]
fn should_use_the_exact_libobs_source_ids() {
    // Identifiants du vrai greffon win-capture d'OBS, jamais inventés : une faute ici
    // produirait une source que libobs refuse de créer, sans dire pourquoi.
    assert_eq!(CaptureKind::Game.libobs_id(), "game_capture");
    assert_eq!(CaptureKind::Window.libobs_id(), "window_capture");
    assert_eq!(CaptureKind::Monitor.libobs_id(), "monitor_capture");
}

#[test]
fn should_accept_a_new_source_name_in_a_scene() {
    assert_eq!(validate_source_name("Jeu", &["Webcam".to_string()]), Ok(()));
}

#[test]
fn should_reject_an_empty_source_name() {
    assert_eq!(validate_source_name("   ", &[]), Err(SceneNameError::Empty));
}

#[test]
fn should_reject_a_source_name_already_used_in_the_same_scene() {
    // Deux sources du même nom dans une scène : libobs les renomme en silence
    // (« Webcam 2 »), et l'écran ne retrouve plus celle qu'il croit désigner.
    assert_eq!(
        validate_source_name("Webcam", &["Webcam".to_string()]),
        Err(SceneNameError::Duplicate)
    );
}

#[test]
fn should_roundtrip_the_capture_targets_message() {
    let msg = EngineMessage::CaptureTargets {
        games: vec![CaptureTarget { id: "LoL".to_string(), label: "League of Legends".to_string() }],
        windows: vec![CaptureTarget { id: "w1".to_string(), label: "Bloc-notes".to_string() }],
        monitors: vec![CaptureTarget { id: "\\\\.\\DISPLAY1".to_string(), label: "Écran 1".to_string() }],
    };
    let line = to_line(&msg).expect("serializes");
    assert!(!line.contains('\n'));
    assert_eq!(parse_engine_message(&line).expect("parses"), msg);
}

#[test]
fn should_roundtrip_every_source_command() {
    let commands = vec![
        ControllerCommand::ListCaptureTargets,
        ControllerCommand::AddCaptureSource {
            scene: "main".to_string(),
            kind: CaptureKind::Game,
            target_id: "LoL".to_string(),
            name: "Jeu".to_string(),
        },
        ControllerCommand::RemoveSource {
            scene: "main".to_string(),
            name: "Jeu".to_string(),
        },
    ];
    for cmd in commands {
        let line = to_line(&cmd).expect("serializes");
        assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
    }
}

#[test]
fn should_carry_each_scenes_own_source_list() {
    // Le panneau doit lire ce que contient CHAQUE scène sans basculer dessus — basculer
    // est une coupe en direct, jamais un coup d'œil gratuit.
    let jeu = SceneInfo {
        name: "Jeu".to_string(),
        has_camera: true,
        background_removal: false,
        circle_mask: false,
        sources: vec![
            SceneSourceInfo { name: "Jeu".to_string(), kind: "game_capture".to_string() },
            SceneSourceInfo { name: "Webcam".to_string(), kind: "dshow_input".to_string() },
        ],
    };
    let msg = EngineMessage::SceneList {
        scenes: vec![SceneInfo::empty("main"), jeu.clone()],
        active: "main".to_string(),
    };
    let line = to_line(&msg).expect("serializes");
    let EngineMessage::SceneList { scenes, .. } = parse_engine_message(&line).expect("parses")
    else {
        panic!("expected a scene_list");
    };
    assert_eq!(scenes[1], jeu);
    assert!(scenes[0].sources.is_empty(), "une scène neuve ne contient rien");
}

proptest! {
    #[test]
    fn should_never_accept_a_source_name_already_in_the_scene(name in "[a-zA-Z0-9]{1,20}") {
        prop_assert_eq!(
            validate_source_name(&name, std::slice::from_ref(&name)),
            Err(SceneNameError::Duplicate)
        );
    }

    #[test]
    fn should_roundtrip_any_capture_target(
        id in "[a-zA-Z0-9 :._-]{0,30}",
        label in "[a-zA-Z0-9 :._-]{0,30}",
    ) {
        let msg = EngineMessage::CaptureTargets {
            games: vec![CaptureTarget { id, label }],
            windows: Vec::new(),
            monitors: Vec::new(),
        };
        let line = to_line(&msg).expect("serializes");
        prop_assert!(!line.contains('\n'));
        prop_assert_eq!(parse_engine_message(&line).expect("parses"), msg);
    }
}
