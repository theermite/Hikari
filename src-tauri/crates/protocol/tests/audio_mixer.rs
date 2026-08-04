//! Audio mixer (B6, tranche 1) — pure contract tests: the volume scale, the level scale,
//! and the wire round-trip. The real libobs sources, volume calls and level meter are
//! integration regime, proven by running the app.

use hikari_protocol::{
    AudioDevice, AudioLevel, AudioSourceInfo, AudioSourceKind, ControllerCommand, EngineMessage,
    METER_FLOOR_DB, db_to_meter_fraction, parse_controller_command, parse_engine_message,
    percent_to_volume, to_line, volume_to_percent,
};
use proptest::prelude::*;

#[test]
fn should_map_full_slider_to_unchanged_volume() {
    // 100 % veut dire « le son tel qu'il arrive », jamais amplifié : le multiplicateur est 1.
    assert_eq!(percent_to_volume(100), 1.0);
}

#[test]
fn should_map_a_silent_slider_to_silence() {
    assert_eq!(percent_to_volume(0), 0.0);
}

#[test]
fn should_clamp_a_slider_beyond_its_range() {
    assert_eq!(percent_to_volume(500), 1.0);
    assert_eq!(percent_to_volume(-20), 0.0);
}

#[test]
fn should_round_trip_a_slider_value() {
    for percent in [0, 25, 50, 75, 100] {
        assert_eq!(volume_to_percent(percent_to_volume(percent)), percent);
    }
}

#[test]
fn should_show_a_full_bar_at_zero_decibels() {
    assert_eq!(db_to_meter_fraction(0.0), 1.0);
}

#[test]
fn should_show_an_empty_bar_at_the_floor() {
    assert_eq!(db_to_meter_fraction(METER_FLOOR_DB), 0.0);
}

#[test]
fn should_show_an_empty_bar_below_the_floor_rather_than_a_negative_one() {
    // libobs signale du silence par -infini : la barre doit rester vide, jamais partir
    // dans le négatif ni devenir NaN.
    assert_eq!(db_to_meter_fraction(-120.0), 0.0);
    assert_eq!(db_to_meter_fraction(f32::NEG_INFINITY), 0.0);
}

#[test]
fn should_show_a_half_bar_at_half_the_floor() {
    assert_eq!(db_to_meter_fraction(METER_FLOOR_DB / 2.0), 0.5);
}

#[test]
fn should_cap_the_bar_above_zero_decibels_rather_than_overflowing() {
    assert_eq!(db_to_meter_fraction(6.0), 1.0);
}

#[test]
fn should_roundtrip_the_audio_device_list() {
    let msg = EngineMessage::AudioDevices {
        inputs: vec![AudioDevice {
            name: "Micro".to_string(),
            device_id: "{0.0.1}".to_string(),
        }],
        outputs: vec![AudioDevice {
            name: "Casque".to_string(),
            device_id: "{0.0.0}".to_string(),
        }],
    };
    let line = to_line(&msg).expect("serializes");
    assert!(!line.contains('\n'));
    assert_eq!(parse_engine_message(&line).expect("parses"), msg);
}

#[test]
fn should_roundtrip_the_audio_source_list() {
    let msg = EngineMessage::AudioSources {
        items: vec![AudioSourceInfo {
            name: "Micro".to_string(),
            kind: AudioSourceKind::Input,
            volume_percent: 80,
            muted: false,
        }],
    };
    let line = to_line(&msg).expect("serializes");
    assert_eq!(parse_engine_message(&line).expect("parses"), msg);
}

#[test]
fn should_roundtrip_the_audio_levels() {
    let msg = EngineMessage::AudioLevels {
        levels: vec![AudioLevel { name: "Micro".to_string(), magnitude_db: -18.5 }],
    };
    let line = to_line(&msg).expect("serializes");
    assert_eq!(parse_engine_message(&line).expect("parses"), msg);
}

#[test]
fn should_roundtrip_every_mixer_command() {
    let commands = vec![
        ControllerCommand::ListAudioDevices,
        ControllerCommand::AddAudioSource {
            device_id: "{0.0.1}".to_string(),
            kind: AudioSourceKind::Input,
            name: "Micro".to_string(),
        },
        ControllerCommand::RemoveAudioSource { name: "Micro".to_string() },
        ControllerCommand::SetAudioVolume { name: "Micro".to_string(), percent: 60 },
        ControllerCommand::SetAudioMuted { name: "Micro".to_string(), muted: true },
    ];
    for cmd in commands {
        let line = to_line(&cmd).expect("serializes");
        assert_eq!(parse_controller_command(&line).expect("parses"), cmd);
    }
}

proptest! {
    #[test]
    fn should_never_produce_a_bar_outside_zero_and_one(db in -200.0f32..60.0) {
        let fraction = db_to_meter_fraction(db);
        prop_assert!((0.0..=1.0).contains(&fraction), "barre hors bornes : {fraction}");
    }

    #[test]
    fn should_never_produce_a_volume_outside_zero_and_one(percent in -1000i32..1000) {
        let volume = percent_to_volume(percent);
        prop_assert!((0.0..=1.0).contains(&volume), "volume hors bornes : {volume}");
    }

    #[test]
    fn should_never_let_a_louder_signal_show_a_shorter_bar(a in -80.0f32..6.0, b in -80.0f32..6.0) {
        // Monotonie : la barre ne doit jamais mentir sur qui est le plus fort.
        if a <= b {
            prop_assert!(db_to_meter_fraction(a) <= db_to_meter_fraction(b));
        }
    }
}
