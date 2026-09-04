//! The mixer's own vocabulary (B6): which side of the sound card, noise suppression,
//! monitoring routing, and the pure conversions between a 0–100 slider and libobs's own
//! decibel/multiplier scales.

use serde::{Deserialize, Serialize};

use crate::platform::{AUDIO_INPUT_KIND, AUDIO_OUTPUT_KIND};

/// Which side of the sound card an audio source listens to (B6).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AudioSourceKind {
    /// A microphone or line-in — what the streamer says.
    Input,
    /// Desktop audio — what the machine plays (game, music, calls).
    Output,
}

impl AudioSourceKind {
    /// The libobs source id to build for this side.
    pub fn libobs_id(self) -> &'static str {
        match self {
            AudioSourceKind::Input => AUDIO_INPUT_KIND,
            AudioSourceKind::Output => AUDIO_OUTPUT_KIND,
        }
    }

    /// Whether offering noise suppression on this side makes sense.
    ///
    /// Only a microphone carries room noise — fan, keyboard, street. Desktop sound is an
    /// already-digital signal: the filter has nothing to remove there, and would damage
    /// music while trying to clean up a voice it cannot find.
    pub fn supports_noise_suppression(self) -> bool {
        matches!(self, AudioSourceKind::Input)
    }
}

/// The libobs filter id for noise suppression — the real obs-filters plugin id, verified
/// 2026-08-04 against obs-studio source.
pub const NOISE_SUPPRESS_FILTER_KIND: &str = "noise_suppress_filter";

/// How the room noise is removed (B6).
///
/// Counter-intuitive but verified twice in the obs-filters source (2026-08-04): the
/// *machine-learning* method is the one with NO dial, and the *older* one is the adjustable
/// one. OBS itself hides the level field when RNNoise is picked.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NoiseMethod {
    /// Speex — the adjustable one. Lighter on the CPU, and its strength is a dial.
    Speex,
    /// RNNoise — the machine-learning one. Cleaner result, no setting at all, costs more CPU.
    Rnnoise,
}

impl NoiseMethod {
    /// The exact value the filter's `method` property expects.
    pub fn libobs_value(self) -> &'static str {
        match self {
            NoiseMethod::Speex => "speex",
            NoiseMethod::Rnnoise => "rnnoise",
        }
    }

    /// Whether this method exposes a strength to set. Only Speex does — showing a dial for
    /// RNNoise would be inventing a setting that does not exist.
    pub fn has_level(self) -> bool {
        matches!(self, NoiseMethod::Speex)
    }
}

/// The libobs property name carrying Speex's strength.
pub const NOISE_LEVEL_PROPERTY: &str = "suppress_level";
/// Strongest suppression Speex accepts, in decibels (obs-filters source, 2026-08-04).
pub const NOISE_LEVEL_MIN_DB: f32 = -60.0;
/// Weakest suppression Speex accepts.
pub const NOISE_LEVEL_MAX_DB: f32 = 0.0;
/// OBS's own default, kept so a Hikari user and an OBS user hear the same thing.
pub const NOISE_LEVEL_DEFAULT_DB: f32 = -30.0;

/// Clamps a Speex strength into the range the filter accepts. A non-finite value falls back
/// to the default rather than reaching libobs.
pub fn clamp_noise_level(level_db: f32) -> f32 {
    if !level_db.is_finite() {
        return NOISE_LEVEL_DEFAULT_DB;
    }
    level_db.clamp(NOISE_LEVEL_MIN_DB, NOISE_LEVEL_MAX_DB)
}

/// One audio device libobs reports on this machine. `device_id` is the exact value the
/// wasapi source's `device_id` property expects, never hand-built.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AudioDevice {
    pub name: String,
    pub device_id: String,
}

/// One entry in the mixer, and its live settings.
///
/// One entry can be backed by TWO libobs sources — see [`crate::wire::ControllerCommand::SetMonitorVolume`]
/// for why. The panel never sees that: it reads one row with two volumes.
///
/// `PartialEq` but not `Eq`: `noise_level_db` is a float.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AudioSourceInfo {
    pub name: String,
    pub kind: AudioSourceKind,
    /// L'appareil réel derrière cette entrée — sans lui, une session sauvegardée ne peut
    /// pas la recréer au lancement suivant.
    pub device_id: String,
    /// 0–100, the slider position for what the AUDIENCE hears — never the raw libobs
    /// multiplier, so the panel never has to know the audio scale.
    pub volume_percent: i32,
    /// 0–100, the slider position for what the STREAMER hears in their headphones.
    /// Meaningful only when `monitoring` includes them.
    pub monitor_volume_percent: i32,
    pub muted: bool,
    /// Whether the streamer hears this source, and whether the audience does.
    pub monitoring: AudioMonitoring,
    /// Whether room-noise suppression is on. Always `false` on a source whose kind does not
    /// support it (see [`AudioSourceKind::supports_noise_suppression`]).
    pub noise_suppression: bool,
    pub noise_method: NoiseMethod,
    /// Speex's strength. Carried even when the method is RNNoise, so switching back and
    /// forth does not lose what the user had set.
    pub noise_level_db: f32,
}

/// One source's current loudness, as libobs measures it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AudioLevel {
    pub name: String,
    /// Magnitude in decibels, ALWAYS finite. `0` is the loudest undistorted signal;
    /// silence is [`METER_FLOOR_DB`]. Build it with [`AudioLevel::new`], never by hand.
    pub magnitude_db: f32,
}

impl AudioLevel {
    /// Builds a level the wire can actually carry, clamping silence and broken readings to
    /// [`METER_FLOOR_DB`].
    ///
    /// WHY this exists (regression 2026-08-04): libobs reports silence as `-inf`, and JSON
    /// has no way to write a non-finite number — `serde_json` emits `null`, which then fails
    /// to parse back as `f32`. The failure is not local: the WHOLE `AudioLevels` message is
    /// rejected, so one muted source froze every other source's bar. A level is clamped at
    /// the boundary rather than trusted from the caller.
    pub fn new(name: impl Into<String>, magnitude_db: f32) -> Self {
        Self {
            name: name.into(),
            magnitude_db: if magnitude_db.is_finite() {
                magnitude_db
            } else if magnitude_db == f32::INFINITY {
                0.0
            } else {
                METER_FLOOR_DB
            },
        }
    }
}

/// Whether a source is played back to the streamer's own ears, and whether the audience
/// hears it too (B6). Mirrors libobs's own three monitoring states.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AudioMonitoring {
    /// The audience hears it, the streamer does not (their ears already hear the room).
    /// libobs's default, and the right one for a microphone on speakers — monitoring a mic
    /// out loud is how a feedback loop starts.
    None,
    /// The streamer hears it, the audience does not. For checking a source privately.
    MonitorOnly,
    /// Both hear it. For a source the machine plays but the streamer's headphones do not
    /// already receive.
    MonitorAndOutput,
}

/// The quietest level the meter shows. Below this the bar is simply empty — a meter that
/// stretched to `-inf` would spend its whole length on silence nobody can hear.
pub const METER_FLOOR_DB: f32 = -60.0;

/// Turns a decibel reading into a `0.0..=1.0` bar length. Linear in decibels, which is how
/// loudness is actually perceived — a linear-in-amplitude bar would sit near zero for every
/// normal speaking level.
pub fn db_to_meter_fraction(db: f32) -> f32 {
    if !db.is_finite() {
        // libobs reports silence as -inf; NaN would come from a broken reading. Both mean
        // "show nothing" rather than "crash the bar".
        return if db == f32::INFINITY { 1.0 } else { 0.0 };
    }
    (1.0 - db / METER_FLOOR_DB).clamp(0.0, 1.0)
}

/// Turns a 0–100 slider into the multiplier libobs applies to the signal. Clamped, so a
/// malformed command can never boost the sound past unity or invert it.
pub fn percent_to_volume(percent: i32) -> f32 {
    percent.clamp(0, 100) as f32 / 100.0
}

/// Turns a libobs multiplier back into a 0–100 slider position.
pub fn volume_to_percent(volume: f32) -> i32 {
    if !volume.is_finite() {
        return 0;
    }
    (volume * 100.0).round().clamp(0.0, 100.0) as i32
}
