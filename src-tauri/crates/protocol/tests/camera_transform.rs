//! Camera transform (B7) contract tests — clamp math + wire round-trip. The real libobs
//! `set_source_position`/`set_source_scale` calls are integration-regime (validated by
//! running the engine, see session 2026-07-24 verification log), same split as every other
//! libobs-backed brick in this codebase.

use hikari_protocol::{
    CAMERA_POSITION_BOUND, CAMERA_SCALE_MAX, CAMERA_SCALE_MIN, CAMERA_SOURCE_NAME,
    ControllerCommand, EngineMessage, clamp_camera_position, clamp_camera_scale,
    lerp_camera_transform, parse_controller_command, parse_engine_message, to_line,
};
use proptest::prelude::*;

/// Une session enregistrée avant le 2026-08-06 ne porte pas le nom de sa caméra : le rejeu
/// retombe alors sur cette valeur, recopiée de l'autre côté de la frontière
/// (`DEFAULT_CAMERA_NAME`, `src/features/scenes/session.ts`). La renommer d'un seul côté
/// ferait silencieusement perdre le cadrage au lancement — ce test casse à la place.
#[test]
fn should_keep_the_camera_name_the_session_replay_falls_back_to() {
    assert_eq!(CAMERA_SOURCE_NAME, "Webcam");
}

#[test]
fn should_pass_through_position_within_bound() {
    assert_eq!(clamp_camera_position(120, -80), (120, -80));
}

#[test]
fn should_clamp_position_above_bound() {
    assert_eq!(
        clamp_camera_position(CAMERA_POSITION_BOUND + 500, CAMERA_POSITION_BOUND + 1),
        (CAMERA_POSITION_BOUND, CAMERA_POSITION_BOUND)
    );
}

#[test]
fn should_clamp_position_below_negative_bound() {
    assert_eq!(
        clamp_camera_position(-CAMERA_POSITION_BOUND - 500, -CAMERA_POSITION_BOUND - 1),
        (-CAMERA_POSITION_BOUND, -CAMERA_POSITION_BOUND)
    );
}

#[test]
fn should_clamp_scale_to_floor() {
    assert_eq!(clamp_camera_scale(0.01), CAMERA_SCALE_MIN);
}

#[test]
fn should_clamp_scale_to_ceiling() {
    assert_eq!(clamp_camera_scale(50.0), CAMERA_SCALE_MAX);
}

#[test]
fn should_pass_through_scale_within_range() {
    assert_eq!(clamp_camera_scale(1.0), 1.0);
}

#[test]
fn should_roundtrip_nudge_camera_command() {
    let cmd = ControllerCommand::NudgeCamera {
        device_id: "usb#vid_046d".to_string(),
        scene: "Jeu".to_string(),
        dx: 40,
        dy: -40,
    };
    let line = to_line(&cmd).expect("serializes");
    assert!(!line.contains('\n'));
    assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
}

#[test]
fn should_roundtrip_scale_camera_command() {
    let cmd = ControllerCommand::ScaleCamera {
        device_id: "usb#vid_046d".to_string(),
        scene: "Jeu".to_string(),
        grow: true,
    };
    let line = to_line(&cmd).expect("serializes");
    assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
}

#[test]
fn should_roundtrip_camera_transform_message() {
    let msg = EngineMessage::CameraTransform {
        device_id: "usb#vid_046d".to_string(),
        scene: "Jeu".to_string(),
        x: 100,
        y: -50,
        scale_percent: 120,
    };
    let line = to_line(&msg).expect("serializes");
    assert_eq!(parse_engine_message(&line).expect("parses"), msg);
}

#[test]
fn should_start_lerp_at_the_from_placement() {
    assert_eq!(lerp_camera_transform((100, 200, 1.0), (300, 400, 1.5), 0.0), (100, 200, 1.0));
}

#[test]
fn should_end_lerp_at_the_to_placement() {
    assert_eq!(lerp_camera_transform((100, 200, 1.0), (300, 400, 1.5), 1.0), (300, 400, 1.5));
}

#[test]
fn should_land_halfway_at_half_progress() {
    assert_eq!(lerp_camera_transform((0, 0, 1.0), (100, 200, 2.0), 0.5), (50, 100, 1.5));
}

#[test]
fn should_clamp_progress_past_one_to_the_to_placement() {
    // A tick landing after the animation's own deadline (a slow frame, a paused process)
    // must still resolve exactly on `to` — never overshoot past it.
    assert_eq!(lerp_camera_transform((0, 0, 1.0), (100, 100, 2.0), 1.8), (100, 100, 2.0));
}

#[test]
fn should_clamp_negative_progress_to_the_from_placement() {
    assert_eq!(lerp_camera_transform((10, 20, 1.0), (30, 40, 2.0), -0.5), (10, 20, 1.0));
}

proptest! {
    #[test]
    fn should_never_exceed_bound_for_any_position(x in any::<i32>(), y in any::<i32>()) {
        let (cx, cy) = clamp_camera_position(x, y);
        prop_assert!((-CAMERA_POSITION_BOUND..=CAMERA_POSITION_BOUND).contains(&cx));
        prop_assert!((-CAMERA_POSITION_BOUND..=CAMERA_POSITION_BOUND).contains(&cy));
    }

    #[test]
    fn should_never_exceed_range_for_any_scale(scale in any::<f32>().prop_filter("finite", |s| s.is_finite())) {
        let clamped = clamp_camera_scale(scale);
        prop_assert!((CAMERA_SCALE_MIN..=CAMERA_SCALE_MAX).contains(&clamped));
    }

    #[test]
    fn should_roundtrip_camera_transform_for_any_value(device_id in any::<String>(), scene in any::<String>(), x in any::<i32>(), y in any::<i32>(), scale_percent in any::<i32>()) {
        let msg = EngineMessage::CameraTransform { device_id, scene, x, y, scale_percent };
        let line = to_line(&msg).expect("serializes");
        prop_assert!(!line.contains('\n'));
        prop_assert_eq!(parse_engine_message(&line).expect("parses"), msg);
    }

    #[test]
    fn should_stay_between_from_and_to_for_any_progress(
        from_x in -1000i32..1000, from_y in -1000i32..1000,
        to_x in -1000i32..1000, to_y in -1000i32..1000,
        progress in 0.0f32..=1.0f32,
    ) {
        let (x, y, _) = lerp_camera_transform((from_x, from_y, 1.0), (to_x, to_y, 1.0), progress);
        prop_assert!(x >= from_x.min(to_x) && x <= from_x.max(to_x));
        prop_assert!(y >= from_y.min(to_y) && y <= from_y.max(to_y));
    }
}
