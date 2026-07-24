//! Camera transform (B7) contract tests — clamp math + wire round-trip. The real libobs
//! `set_source_position`/`set_source_scale` calls are integration-regime (validated by
//! running the engine, see session 2026-07-24 verification log), same split as every other
//! libobs-backed brick in this codebase.

use hikari_protocol::{
    CAMERA_POSITION_BOUND, CAMERA_SCALE_MAX, CAMERA_SCALE_MIN, ControllerCommand, EngineMessage,
    clamp_camera_position, clamp_camera_scale, parse_controller_command, parse_engine_message,
    to_line,
};
use proptest::prelude::*;

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
    let cmd = ControllerCommand::NudgeCamera { dx: 40, dy: -40 };
    let line = to_line(&cmd).expect("serializes");
    assert!(!line.contains('\n'));
    assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
}

#[test]
fn should_roundtrip_scale_camera_command() {
    let cmd = ControllerCommand::ScaleCamera { grow: true };
    let line = to_line(&cmd).expect("serializes");
    assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
}

#[test]
fn should_roundtrip_camera_transform_message() {
    let msg = EngineMessage::CameraTransform { x: 100, y: -50, scale_percent: 120 };
    let line = to_line(&msg).expect("serializes");
    assert_eq!(parse_engine_message(&line).expect("parses"), msg);
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
    fn should_roundtrip_camera_transform_for_any_value(x in any::<i32>(), y in any::<i32>(), scale_percent in any::<i32>()) {
        let msg = EngineMessage::CameraTransform { x, y, scale_percent };
        let line = to_line(&msg).expect("serializes");
        prop_assert!(!line.contains('\n'));
        prop_assert_eq!(parse_engine_message(&line).expect("parses"), msg);
    }
}
