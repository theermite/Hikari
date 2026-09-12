//! Ce que le fil de lecture stdin transmet au fil winit/libobs — extrait de `main.rs` le
//! 2026-09-09, ce fichier ayant atteint le plafond BLOQUANT de 500 lignes. Pure donnée,
//! aucun comportement : cette énumération ne change pas en la déplaçant.

/// Commands forwarded from the stdin-reader thread to the event loop (winit's
/// `EventLoopProxy` is the documented cross-thread wake-up mechanism — libobs calls only
/// ever happen on the winit/event-loop thread, never on the stdin-reader thread itself).
pub(crate) enum EngineEvent {
    Exit,
    StartStream,
    StopStream,
    StartMultistream {
        targets: Vec<hikari_protocol::StreamTarget>,
    },
    StopMultistream,
    AddCamera {
        device_id: String,
        scene: String,
    },
    SetBackgroundRemoval {
        device_id: String,
        scene: String,
        enabled: bool,
    },
    SetMaskShape {
        device_id: String,
        scene: String,
        shape: hikari_protocol::MaskShape,
    },
    RemoveCamera {
        device_id: String,
        scene: String,
    },
    RestartCamera {
        device_id: String,
    },
    NudgeCamera {
        device_id: String,
        scene: String,
        dx: i32,
        dy: i32,
    },
    ScaleCamera {
        device_id: String,
        scene: String,
        grow: bool,
    },
    CreateScene {
        name: String,
    },
    SwitchScene {
        name: String,
        duration_ms: u32,
    },
    DeleteScene {
        name: String,
    },
    ListAudioDevices,
    AddAudioSource {
        device_id: String,
        kind: hikari_protocol::AudioSourceKind,
        name: String,
    },
    RemoveAudioSource {
        name: String,
    },
    SetAudioVolume {
        name: String,
        percent: i32,
    },
    SetAudioMuted {
        name: String,
        muted: bool,
    },
    SetAudioMonitoring {
        name: String,
        monitoring: hikari_protocol::AudioMonitoring,
    },
    SetNoiseSettings {
        name: String,
        enabled: bool,
        method: hikari_protocol::NoiseMethod,
        level_db: f32,
    },
    SetMonitorVolume {
        name: String,
        percent: i32,
    },
    ListCaptureTargets,
    AddCaptureSource {
        scene: String,
        kind: hikari_protocol::SourceKind,
        target_id: String,
        name: String,
    },
    RemoveSource {
        scene: String,
        name: String,
    },
    ReorderSource {
        scene: String,
        name: String,
        direction: hikari_protocol::SourceOrder,
    },
    SetSourceOrder {
        scene: String,
        name: String,
        position: i32,
    },
    SetSourceTransform {
        scene: String,
        name: String,
        x: i32,
        y: i32,
        scale_percent: i32,
    },
    SetSourceLocked {
        scene: String,
        name: String,
        locked: bool,
    },
    SetSourceVisible {
        scene: String,
        name: String,
        visible: bool,
    },
    SetTextSettings {
        scene: String,
        name: String,
        settings: hikari_protocol::TextSettings,
    },
    SetTextContent {
        scene: String,
        name: String,
        text: String,
    },
    RequestSceneList,
}
