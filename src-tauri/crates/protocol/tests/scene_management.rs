//! Multi-scene (tranche 1) contract tests — name validation + wire round-trip. The real
//! libobs `scene()`/`set_to_channel()` calls are integration-regime (validated by running
//! the engine), same split as every other libobs-backed brick in this codebase.

use hikari_protocol::{
    ControllerCommand, EngineMessage, SceneDeleteError, SceneInfo, SceneNameError,
    parse_controller_command, parse_engine_message, to_line, validate_scene_deletion,
    validate_scene_name,
};
use proptest::prelude::*;

#[test]
fn should_accept_new_unique_name() {
    assert_eq!(validate_scene_name("Jeu", &["Discussion".to_string()]), Ok(()));
}

#[test]
fn should_reject_empty_name() {
    assert_eq!(validate_scene_name("", &[]), Err(SceneNameError::Empty));
    assert_eq!(validate_scene_name("   ", &[]), Err(SceneNameError::Empty));
}

#[test]
fn should_reject_duplicate_name() {
    assert_eq!(
        validate_scene_name("Jeu", &["Jeu".to_string()]),
        Err(SceneNameError::Duplicate)
    );
}

#[test]
fn should_roundtrip_create_scene_command() {
    let cmd = ControllerCommand::CreateScene { name: "Jeu".to_string() };
    let line = to_line(&cmd).expect("serializes");
    assert!(!line.contains('\n'));
    assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
}

#[test]
fn should_roundtrip_switch_scene_command() {
    let cmd = ControllerCommand::SwitchScene { name: "Discussion".to_string() };
    let line = to_line(&cmd).expect("serializes");
    assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
}

#[test]
fn should_roundtrip_scene_list_message() {
    let msg = EngineMessage::SceneList {
        scenes: vec![SceneInfo::empty("main"), SceneInfo::empty("Jeu")],
        active: "main".to_string(),
    };
    let line = to_line(&msg).expect("serializes");
    assert_eq!(parse_engine_message(&line).expect("parses"), msg);
}

#[test]
fn should_carry_each_scene_own_camera_and_filter_state() {
    // Étape 3, point 4 : la liste dit ce que contient CHAQUE scène, pas seulement la scène
    // active — sinon le panneau devrait basculer sur une scène pour savoir ce qu'elle porte.
    let jeu = SceneInfo {
        name: "Jeu".to_string(),
        has_camera: true,
        background_removal: true,
        circle_mask: false,
        sources: Vec::new(),
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
    assert!(!scenes[0].has_camera);
}

#[test]
fn should_roundtrip_delete_scene_command() {
    let cmd = ControllerCommand::DeleteScene { name: "Jeu".to_string() };
    let line = to_line(&cmd).expect("serializes");
    assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
}

#[test]
fn should_accept_deleting_a_scene_when_others_remain() {
    let existing = vec!["main".to_string(), "Jeu".to_string()];
    assert_eq!(validate_scene_deletion("Jeu", &existing), Ok(()));
}

#[test]
fn should_reject_deleting_the_last_scene() {
    // Sans scène, le canal de sortie n'a plus rien à diffuser : l'aperçu et le direct
    // tomberaient au noir sans que rien ne l'explique.
    let existing = vec!["main".to_string()];
    assert_eq!(
        validate_scene_deletion("main", &existing),
        Err(SceneDeleteError::LastScene)
    );
}

#[test]
fn should_reject_deleting_an_unknown_scene() {
    let existing = vec!["main".to_string(), "Jeu".to_string()];
    assert_eq!(
        validate_scene_deletion("Absente", &existing),
        Err(SceneDeleteError::Unknown)
    );
}

proptest! {
    #[test]
    fn should_never_accept_a_name_already_in_the_list(name in "[a-zA-Z0-9]{1,20}") {
        // Non-blank by construction (no space in the alphabet) — isolates the duplicate
        // rule from the empty rule, which `should_reject_empty_name` covers separately.
        let existing = vec![name.clone()];
        prop_assert_eq!(validate_scene_name(&name, &existing), Err(SceneNameError::Duplicate));
    }

    #[test]
    fn should_roundtrip_scene_list_for_any_value(names in prop::collection::vec("[a-zA-Z0-9]{0,10}", 0..5), active in any::<String>()) {
        let scenes = names.iter().map(SceneInfo::empty).collect::<Vec<_>>();
        let msg = EngineMessage::SceneList { scenes, active };
        let line = to_line(&msg).expect("serializes");
        prop_assert!(!line.contains('\n'));
        prop_assert_eq!(parse_engine_message(&line).expect("parses"), msg);
    }

    #[test]
    fn should_never_delete_when_it_is_the_only_scene(name in "[a-zA-Z0-9]{1,20}") {
        // Quel que soit son nom, une scène seule au monde ne se supprime jamais.
        prop_assert_eq!(
            validate_scene_deletion(&name, std::slice::from_ref(&name)),
            Err(SceneDeleteError::LastScene)
        );
    }

    #[test]
    fn should_never_delete_a_name_absent_from_the_list(
        name in "[a-zA-Z0-9]{1,20}",
        others in prop::collection::vec("[a-zA-Z0-9]{1,20}", 2..5),
    ) {
        // `name` porte un préfixe qu'aucun `others` ne peut avoir : absence garantie.
        let absent = format!("__{name}");
        prop_assert_eq!(validate_scene_deletion(&absent, &others), Err(SceneDeleteError::Unknown));
    }
}
