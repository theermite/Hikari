//! Preflight — hardware detection + safe default + Go Live gate (B9, F-002/F-003).
//!
//! Pure decision logic over the encoder list the engine already reports
//! (`EngineMessage::Encoders`, API proven at the B0.0 spike) — this module never calls
//! libobs itself, it only interprets what was detected. F-003: the capability is always
//! DETECTED, never presumed — an engine that reports nothing yields a blocked Go Live,
//! not a silent guess.

/// The video encoder picked as the safe default, and whether it is hardware-accelerated
/// (mirrors the `hardware` flag `stream::start_stream` already reports — Go Live must
/// never claim hardware encoding it did not detect).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SafeEncoder {
    pub name: String,
    pub hardware: bool,
}

/// Why Go Live is blocked — the ONLY failure this preflight step can report today: no
/// usable encoder was detected. Closed enum so a caller cannot invent a reason preflight
/// never checked.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PreflightError {
    NoEncoderDetected,
}

/// Picks the safe default encoder from what the engine actually reported: NVENC
/// (hardware) if present, else the X264 software fallback, else `None` — never a guess.
/// `available` holds the engine's own `Debug`-formatted `ObsVideoEncoderType` strings
/// (`EngineMessage::Encoders`, e.g. `"OBS_NVENC_H264_TEX"`, `"OBS_X264"`); matching by
/// substring keeps this pure function decoupled from the libobs-linked enum, which only
/// the engine process (separate, ADR-013) can even compile against.
pub fn pick_safe_encoder(available: &[String]) -> Option<SafeEncoder> {
    if let Some(nvenc) = available.iter().find(|e| e.contains("NVENC")) {
        return Some(SafeEncoder { name: nvenc.clone(), hardware: true });
    }
    available.iter().find(|e| e.contains("X264")).map(|x264| SafeEncoder { name: x264.clone(), hardware: false })
}

/// The Go Live gate: allowed only when a safe encoder was actually detected. An empty or
/// unrecognized encoder list blocks Go Live instead of falling back to an assumed default
/// (F-003) — the alternative (guessing NVENC) is exactly the silent capability presumption
/// this brick exists to prevent.
pub fn go_live_allowed(available: &[String]) -> Result<SafeEncoder, PreflightError> {
    pick_safe_encoder(available).ok_or(PreflightError::NoEncoderDetected)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_detect_available_encoders() {
        let available = vec!["OBS_NVENC_H264_TEX".to_string(), "OBS_X264".to_string()];
        let picked = pick_safe_encoder(&available).expect("NVENC present must be detected");
        assert_eq!(picked, SafeEncoder { name: "OBS_NVENC_H264_TEX".to_string(), hardware: true });
    }

    #[test]
    fn should_pick_safe_default_when_detected() {
        // No NVENC on this machine: the software encoder is the safe default, and it is
        // reported as non-hardware — never silently claimed as accelerated.
        let available = vec!["OBS_X264".to_string()];
        let picked = pick_safe_encoder(&available).expect("X264 present must be detected");
        assert_eq!(picked, SafeEncoder { name: "OBS_X264".to_string(), hardware: false });
    }

    #[test]
    fn should_prefer_hardware_encoder_when_both_available() {
        // Order in the list must not matter: NVENC wins even listed second.
        let available = vec!["OBS_X264".to_string(), "OBS_NVENC_H264_TEX".to_string()];
        let picked = pick_safe_encoder(&available).expect("both present, NVENC must win");
        assert!(picked.hardware, "hardware encoder must be preferred over software");
    }

    #[test]
    fn should_block_golive_when_precheck_fails() {
        // Nothing detected at all (e.g. driver failure) — Go Live must refuse, never
        // presume a default that was never confirmed (F-003).
        assert_eq!(go_live_allowed(&[]), Err(PreflightError::NoEncoderDetected));
    }

    #[test]
    fn should_block_golive_when_encoders_are_unrecognized() {
        // A non-empty list that contains neither NVENC nor X264 (an encoder family this
        // preflight step doesn't know how to judge safe) must still block, not guess.
        let available = vec!["OBS_QSV_H264".to_string()];
        assert_eq!(go_live_allowed(&available), Err(PreflightError::NoEncoderDetected));
    }
}
