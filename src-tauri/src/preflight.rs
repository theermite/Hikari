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

/// Why Go Live is blocked. Closed enum so a caller cannot invent a reason preflight never
/// checked.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PreflightError {
    /// No usable encoder was detected.
    NoEncoderDetected,
    /// The measured upload speed cannot sustain the bitrate this stream would send —
    /// the real cause behind Jay's ~65 % dropped-frames live (2026-09-12): the composition
    /// chosen was never checked against the CONNECTION, only the screen.
    BandwidthInsufficient {
        measured_kbps: u32,
        required_kbps: u32,
    },
}

/// Picks the safe default encoder from what the engine actually reported: NVENC
/// (hardware) if present, else the X264 software fallback, else `None` — never a guess.
/// `available` holds the engine's own `Debug`-formatted `ObsVideoEncoderType` strings
/// (`EngineMessage::Encoders`, e.g. `"OBS_NVENC_H264_TEX"`, `"OBS_X264"`); matching by
/// substring keeps this pure function decoupled from the libobs-linked enum, which only
/// the engine process (separate, ADR-013) can even compile against.
pub fn pick_safe_encoder(available: &[String]) -> Option<SafeEncoder> {
    if let Some(nvenc) = available.iter().find(|e| e.contains("NVENC")) {
        return Some(SafeEncoder {
            name: nvenc.clone(),
            hardware: true,
        });
    }
    available
        .iter()
        .find(|e| e.contains("X264"))
        .map(|x264| SafeEncoder {
            name: x264.clone(),
            hardware: false,
        })
}

/// The Go Live gate: allowed only when a safe encoder was actually detected. An empty or
/// unrecognized encoder list blocks Go Live instead of falling back to an assumed default
/// (F-003) — the alternative (guessing NVENC) is exactly the silent capability presumption
/// this brick exists to prevent.
pub fn go_live_allowed(available: &[String]) -> Result<SafeEncoder, PreflightError> {
    pick_safe_encoder(available).ok_or(PreflightError::NoEncoderDetected)
}

/// Marge de sécurité entre le débit MESURÉ et le débit REQUIS : une connexion mesurée à
/// exactement le débit choisi n'a aucune marge pour une fluctuation réelle (le réseau
/// n'est jamais parfaitement stable seconde après seconde). `required_kbps` doit donc
/// tenir dans 80 % du débit mesuré — le principe même du module `encoding.rs` :
/// « descendre vaut mieux que perdre ».
const MARGE_MAX: f64 = 0.8;

/// Le débit choisi tient-il vraiment sur cette connexion ? `measured_kbps` vient d'une
/// mesure d'upload réelle (`bandwidth::measure_upload_kbps`, B9 pré-vol) ; `required_kbps`
/// est le débit que ce direct enverrait réellement — le réglage manuel de l'utilisateur
/// (B-settings) s'il en a posé un, sinon le même calcul qu'au démarrage du direct
/// (`hikari_protocol::bitrate_kbps`).
pub fn bandwidth_allows(measured_kbps: u32, required_kbps: u32) -> Result<(), PreflightError> {
    let seuil = (f64::from(measured_kbps) * MARGE_MAX) as u32;
    if required_kbps <= seuil {
        Ok(())
    } else {
        Err(PreflightError::BandwidthInsufficient {
            measured_kbps,
            required_kbps,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_detect_available_encoders() {
        let available = vec!["OBS_NVENC_H264_TEX".to_string(), "OBS_X264".to_string()];
        let picked = pick_safe_encoder(&available).expect("NVENC present must be detected");
        assert_eq!(
            picked,
            SafeEncoder {
                name: "OBS_NVENC_H264_TEX".to_string(),
                hardware: true
            }
        );
    }

    #[test]
    fn should_pick_safe_default_when_detected() {
        // No NVENC on this machine: the software encoder is the safe default, and it is
        // reported as non-hardware — never silently claimed as accelerated.
        let available = vec!["OBS_X264".to_string()];
        let picked = pick_safe_encoder(&available).expect("X264 present must be detected");
        assert_eq!(
            picked,
            SafeEncoder {
                name: "OBS_X264".to_string(),
                hardware: false
            }
        );
    }

    #[test]
    fn should_prefer_hardware_encoder_when_both_available() {
        // Order in the list must not matter: NVENC wins even listed second.
        let available = vec!["OBS_X264".to_string(), "OBS_NVENC_H264_TEX".to_string()];
        let picked = pick_safe_encoder(&available).expect("both present, NVENC must win");
        assert!(
            picked.hardware,
            "hardware encoder must be preferred over software"
        );
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
        assert_eq!(
            go_live_allowed(&available),
            Err(PreflightError::NoEncoderDetected)
        );
    }

    #[test]
    fn should_allow_when_the_connection_easily_covers_the_bitrate() {
        assert_eq!(bandwidth_allows(6000, 4500), Ok(()));
    }

    #[test]
    fn should_block_when_the_connection_cannot_sustain_the_bitrate() {
        // Le cas réel de Jay le 2026-09-12 : composition 1080p60 (débit 6000), mais une
        // connexion qui ne tient pas ce débit — d'où ~65 % de pertes d'images.
        assert_eq!(
            bandwidth_allows(3000, 6000),
            Err(PreflightError::BandwidthInsufficient {
                measured_kbps: 3000,
                required_kbps: 6000,
            })
        );
    }

    #[test]
    fn should_require_headroom_not_just_a_higher_measured_speed() {
        // Mesuré tout juste au-dessus du requis (aucune marge) : une connexion réelle
        // fluctue seconde après seconde, un débit collé au plafond finit par décrocher.
        assert_eq!(
            bandwidth_allows(6000, 5000),
            Err(PreflightError::BandwidthInsufficient {
                measured_kbps: 6000,
                required_kbps: 5000,
            })
        );
    }

    #[test]
    fn should_allow_exactly_at_the_eighty_percent_threshold() {
        assert_eq!(bandwidth_allows(5000, 4000), Ok(()));
    }
}
