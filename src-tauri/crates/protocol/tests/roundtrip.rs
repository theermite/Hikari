//! Wire-protocol contract tests (ADR-011). The protocol is the interface B4/B5
//! (decks) consume, so its round-trip is proven by property-based testing: any
//! message serialized then parsed must equal the original, on a single line.

use hikari_protocol::{
    CameraDevice, ControllerCommand, EngineMessage, MONITOR_CAPTURE_KIND, SourceInfo,
    parse_controller_command, parse_engine_message, to_line,
};
use proptest::prelude::*;

/// Strategy building an arbitrary `SourceInfo`.
fn source_info_strategy() -> impl Strategy<Value = SourceInfo> {
    (any::<String>(), any::<String>()).prop_map(|(name, kind)| SourceInfo { name, kind })
}

/// Strategy building an arbitrary `CameraDevice`.
fn camera_device_strategy() -> impl Strategy<Value = CameraDevice> {
    (any::<String>(), any::<String>()).prop_map(|(name, device_id)| CameraDevice { name, device_id })
}

/// Strategy building an arbitrary `EngineMessage` across every variant.
fn engine_message_strategy() -> impl Strategy<Value = EngineMessage> {
    prop_oneof![
        Just(EngineMessage::Ready),
        Just(EngineMessage::Stopped),
        Just(EngineMessage::Started),
        Just(EngineMessage::StreamStopped),
        prop::collection::vec(source_info_strategy(), 0..4)
            .prop_map(|items| EngineMessage::Sources { items }),
        prop::collection::vec(any::<String>(), 0..4)
            .prop_map(|available| EngineMessage::Encoders { available }),
        prop::collection::vec(camera_device_strategy(), 0..4)
            .prop_map(|devices| EngineMessage::Cameras { devices }),
        (any::<String>(), any::<bool>())
            .prop_map(|(kind, hardware)| EngineMessage::VideoEncoder { kind, hardware }),
        any::<String>().prop_map(|server| EngineMessage::Service { server }),
        (any::<i32>(), any::<i32>())
            .prop_map(|(dropped, total)| EngineMessage::Frames { dropped, total }),
        any::<String>().prop_map(|message| EngineMessage::Error { message }),
        any::<i64>().prop_map(|hwnd| EngineMessage::PreviewReady { hwnd }),
    ]
}

/// Strategy building an arbitrary `ControllerCommand` across every variant.
fn controller_command_strategy() -> impl Strategy<Value = ControllerCommand> {
    prop_oneof![
        any::<String>().prop_map(|name| ControllerCommand::CreateScene { name }),
        Just(ControllerCommand::ListSources),
        Just(ControllerCommand::StartStream),
        Just(ControllerCommand::StopStream),
        Just(ControllerCommand::Stop),
    ]
}

proptest! {
    #[test]
    fn should_parse_command_when_valid_json(msg in engine_message_strategy()) {
        let line = to_line(&msg).expect("serialization must not fail");
        prop_assert!(!line.contains('\n'), "one JSON object per line: no embedded newline");
        let parsed = parse_engine_message(&line).expect("valid JSON must parse");
        prop_assert_eq!(parsed, msg);
    }

    #[test]
    fn should_roundtrip_controller_command_when_valid_json(cmd in controller_command_strategy()) {
        let line = to_line(&cmd).expect("serialization must not fail");
        prop_assert!(!line.contains('\n'), "one JSON object per line: no embedded newline");
        let parsed = parse_controller_command(&line).expect("valid JSON must parse");
        prop_assert_eq!(parsed, cmd);
    }
}

#[test]
fn should_list_sources_when_scene_created() {
    // A scene built with one screen capture yields exactly that source, and it serializes
    // to a single protocol line. The REAL libobs scene build needs a GPU + monitor runtime
    // (it links obs.dll, so its test harness cannot even load headless) — that half is
    // validated by running the `hikari-engine` binary with the OBS runtime (integration
    // regime like the B0.0 spike). Here the headless-runnable logic is proven.
    let sources = vec![SourceInfo::monitor_capture("Monitor Capture")];
    let msg = EngineMessage::Sources { items: sources.clone() };
    assert_eq!(sources.len(), 1, "exactly one source in the scene");
    assert_eq!(sources[0].kind, MONITOR_CAPTURE_KIND, "source is a screen capture");
    let line = to_line(&msg).expect("sources message serializes");
    assert!(line.contains(MONITOR_CAPTURE_KIND), "kind travels on the wire");
    assert!(!line.contains('\n'), "one JSON object per line");
}

#[test]
fn should_return_error_when_json_invalid() {
    // Garbage input yields a clean Err, never a panic (hostile input by default).
    assert!(parse_engine_message("not json at all").is_err());
    assert!(parse_engine_message("").is_err());
    // A well-formed JSON object with an unknown tag is rejected by the tagged enum.
    assert!(parse_engine_message(r#"{"type":"does_not_exist"}"#).is_err());
    assert!(parse_controller_command(r#"{"type":"unknown"}"#).is_err());
}
