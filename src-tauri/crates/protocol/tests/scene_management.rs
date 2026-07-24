//! Multi-scene (tranche 1) contract tests — name validation + wire round-trip. The real
//! libobs `scene()`/`set_to_channel()` calls are integration-regime (validated by running
//! the engine), same split as every other libobs-backed brick in this codebase.

use hikari_protocol::{
    ControllerCommand, EngineMessage, SceneNameError, parse_controller_command,
    parse_engine_message, to_line, validate_scene_name,
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
        names: vec!["main".to_string(), "Jeu".to_string()],
        active: "main".to_string(),
    };
    let line = to_line(&msg).expect("serializes");
    assert_eq!(parse_engine_message(&line).expect("parses"), msg);
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
        let msg = EngineMessage::SceneList { names, active };
        let line = to_line(&msg).expect("serializes");
        prop_assert!(!line.contains('\n'));
        prop_assert_eq!(parse_engine_message(&line).expect("parses"), msg);
    }
}
