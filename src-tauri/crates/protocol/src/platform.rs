//! Every libobs source identifier that changes with the operating system, in ONE place.
//!
//! WHY this module exists: these ids are the ONLY thing in the shared protocol that is
//! not portable. `wasapi_input_capture` is what the Windows `win-wasapi` plugin registers;
//! Linux registers `pulse_input_capture` through `linux-pulseaudio`, and screen capture
//! goes through PipeWire or X11 rather than `monitor_capture`. Scattered across theme
//! modules, a port has to hunt them down one by one and will miss one silently — a missing
//! id does not fail to compile, it fails at runtime as "source kind unknown", on a
//! machine the porter may not have.
//!
//! So: whoever ports Hikari to another system reads this file, and only this file, to know
//! the full surface. Windows is the only system shipped today (`libobs-rs` is tested on
//! Windows and Linux; macOS has no working build upstream — verified 2026-09-04).
//!
//! Two literals still live outside this module, and it is not an oversight:
//! `crates/engine/src/audio.rs` and `camera.rs` pass the id as a macro argument to
//! `libobs-simple`, which needs a literal there. They are pinned by the tests below,
//! which is what makes the drift visible instead of silent.

/// Microphone / line-in capture — what the streamer says.
pub const AUDIO_INPUT_KIND: &str = "wasapi_input_capture";

/// Speaker / desktop-audio capture — what the machine plays.
pub const AUDIO_OUTPUT_KIND: &str = "wasapi_output_capture";

/// Monitor (whole screen) capture.
pub const MONITOR_CAPTURE_KIND: &str = "monitor_capture";

/// Single-window capture.
pub const WINDOW_CAPTURE_KIND: &str = "window_capture";

/// Game / fullscreen-application capture — the fast path, hooks the app directly.
pub const GAME_CAPTURE_KIND: &str = "game_capture";

/// Webcam capture (DirectShow on Windows).
pub const CAMERA_KIND: &str = "dshow_input";

#[cfg(test)]
mod tests {
    use super::*;

    /// Pins the exact ids libobs answers to. A typo here is not a compile error — it is a
    /// source that never appears, at runtime, with no message naming the cause. These
    /// values were each verified against the obs-studio plugin that registers them
    /// (win-wasapi 2026-08-04, win-dshow B-cam, win-capture 2026-08-05).
    #[test]
    fn should_pin_the_windows_source_identifiers() {
        assert_eq!(AUDIO_INPUT_KIND, "wasapi_input_capture");
        assert_eq!(AUDIO_OUTPUT_KIND, "wasapi_output_capture");
        assert_eq!(MONITOR_CAPTURE_KIND, "monitor_capture");
        assert_eq!(WINDOW_CAPTURE_KIND, "window_capture");
        assert_eq!(GAME_CAPTURE_KIND, "game_capture");
        assert_eq!(CAMERA_KIND, "dshow_input");
    }

    /// The engine passes two of these ids as macro literals, where a constant cannot go.
    /// This test reads those files and fails if either literal drifts from the constant —
    /// the one place the duplication could rot in silence.
    #[test]
    fn should_keep_the_engine_macro_literals_in_step() {
        let engine = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("crates/")
            .join("engine")
            .join("src");

        let audio = std::fs::read_to_string(engine.join("audio.rs")).expect("engine audio.rs");
        assert!(
            audio.contains(&format!("\"{AUDIO_INPUT_KIND}\"")),
            "engine/src/audio.rs no longer carries the literal {AUDIO_INPUT_KIND:?}"
        );

        let camera = std::fs::read_to_string(engine.join("camera.rs")).expect("engine camera.rs");
        assert!(
            camera.contains(&format!("\"{CAMERA_KIND}\"")),
            "engine/src/camera.rs no longer carries the literal {CAMERA_KIND:?}"
        );
    }
}
