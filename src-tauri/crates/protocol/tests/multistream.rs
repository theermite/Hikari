//! Multistream wire-protocol contract tests (B3, horizontal-only — vertical is deferred to
//! its own spike, see PET B3/B0.2). Same round-trip discipline as `roundtrip.rs`: any
//! message serialized then parsed must equal the original, one JSON object per line.

use hikari_protocol::{
    ControllerCommand, EngineMessage, MultistreamError, StreamTarget, parse_controller_command,
    parse_engine_message, to_line, validate_targets,
};
use proptest::prelude::*;

fn target(id: &str, server: &str) -> StreamTarget {
    StreamTarget { id: id.to_string(), server: server.to_string() }
}

fn stream_target_strategy() -> impl Strategy<Value = StreamTarget> {
    (any::<String>(), any::<String>()).prop_map(|(id, server)| StreamTarget { id, server })
}

#[test]
fn should_open_n_outputs_when_multistream() {
    // A valid batch of N distinct targets is accepted, and every target survives the wire
    // round-trip intact — this is the headless-provable half of "N/N plateformes atteintes"
    // (the real libobs output opening is validated by running the engine, see multistream.rs).
    let targets = vec![
        target("twitch", "rtmp://live.twitch.tv/app"),
        target("youtube", "rtmp://a.rtmp.youtube.com/live2"),
    ];
    assert!(validate_targets(&targets).is_ok(), "2 distinct targets must validate");

    let cmd = ControllerCommand::StartMultistream { targets: targets.clone() };
    let line = to_line(&cmd).expect("serialization must not fail");
    assert!(!line.contains('\n'), "one JSON object per line");
    let parsed = parse_controller_command(&line).expect("valid JSON must parse");
    match parsed {
        ControllerCommand::StartMultistream { targets: parsed_targets } => {
            assert_eq!(parsed_targets.len(), 2, "N/N targets survive the wire");
            assert_eq!(parsed_targets, targets);
        }
        other => panic!("expected StartMultistream, got {other:?}"),
    }
}

#[test]
fn should_reject_empty_targets() {
    assert_eq!(validate_targets(&[]), Err(MultistreamError::NoTargets));
}

#[test]
fn should_reject_duplicate_target_ids() {
    let targets = vec![target("twitch", "rtmp://a"), target("twitch", "rtmp://b")];
    assert_eq!(
        validate_targets(&targets),
        Err(MultistreamError::DuplicateId { id: "twitch".to_string() })
    );
}

#[test]
fn should_stop_multistream_as_no_op_shaped_command() {
    // StopMultistream carries no data (mirrors StopStream) — this just proves it survives
    // the wire, since there is no field to assert on.
    let line = to_line(&ControllerCommand::StopMultistream).expect("serializes");
    let parsed = parse_controller_command(&line).expect("parses");
    assert_eq!(parsed, ControllerCommand::StopMultistream);
}

proptest! {
    #[test]
    fn should_roundtrip_stream_target(t in stream_target_strategy()) {
        let cmd = ControllerCommand::StartMultistream { targets: vec![t.clone()] };
        let line = to_line(&cmd).expect("serialization must not fail");
        prop_assert!(!line.contains('\n'));
        let parsed = parse_controller_command(&line).expect("valid JSON must parse");
        prop_assert_eq!(parsed, ControllerCommand::StartMultistream { targets: vec![t] });
    }

    #[test]
    fn should_report_per_platform_status(
        id in any::<String>(),
        hardware in any::<bool>(),
        dropped in any::<i32>(),
        total in any::<i32>(),
        message in any::<String>(),
    ) {
        // Every per-platform message round-trips — B3's acceptance criterion "aucun échec
        // silencieux" depends on PlatformError surviving the wire exactly like the others.
        for msg in [
            EngineMessage::PlatformStarted { id: id.clone(), hardware },
            EngineMessage::PlatformFrames { id: id.clone(), dropped, total },
            EngineMessage::PlatformStopped { id: id.clone() },
            EngineMessage::PlatformError { id: id.clone(), message: message.clone() },
        ] {
            let line = to_line(&msg).expect("serialization must not fail");
            prop_assert!(!line.contains('\n'));
            let parsed = parse_engine_message(&line).expect("valid JSON must parse");
            prop_assert_eq!(parsed, msg);
        }
    }
}
