//! Journal des directs : ce que le moteur dit des images perdues, écrit dans un fichier.
//!
//! Pourquoi : Jay a eu deux directs à « 6x % » d'images perdues (720p60, 5 000 kb/s) et
//! personne ne pouvait dire quand ni pourquoi — le moteur envoyait bien `Frames` toutes les
//! 2 secondes, mais rien ne le gardait. Sans trace, le prochain direct restait une
//! supposition (2026-10-14).
//!
//! Ce module est PUR : il reçoit des messages du moteur et rend la ligne à écrire, jamais
//! d'accès disque ici (`append_line` est à part). Il ne retient aucune clé, aucun compte,
//! aucune donnée personnelle : des compteurs, des réglages d'encodage et des heures.

use std::io::Write;
use std::path::Path;

use hikari_protocol::EngineMessage;
use tauri::AppHandle;

use crate::encoding_settings::{saved_bitrate_kbps, saved_composition, saved_encoder};

/// Intervalle sans nouvelle perte au bout duquel une ligne est écrite quand même, pour que
/// le fichier montre « tout va bien » et pas seulement les mauvais moments.
const HEARTBEAT_SECS: u64 = 30;

/// Longueur maximale d'un message d'erreur recopié — le journal doit rester lisible.
const MAX_ERROR_CHARS: usize = 160;

/// Taux de perte en pourcent, 0 quand rien n'a encore été compté.
pub fn drop_rate_percent(dropped: i32, total: i32) -> f64 {
    if total <= 0 {
        return 0.0;
    }
    f64::from(dropped.max(0)) * 100.0 / f64::from(total)
}

/// Jour civil (UTC) correspondant à un nombre de jours depuis 1970-01-01.
/// Algorithme de Howard Hinnant (« civil from days »), valable pour tout le calendrier
/// grégorien — pas de dépendance de date pour 15 lignes de calcul.
fn civil_from_days(days: i64) -> (i64, u32, u32) {
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let year = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let month = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (year + i64::from(month <= 2), month, day)
}

/// Le jour, pour nommer le fichier : `2026-10-14`.
pub fn day_stamp(unix_secs: u64) -> String {
    let (year, month, day) = civil_from_days((unix_secs / 86_400) as i64);
    format!("{year:04}-{month:02}-{day:02}")
}

/// L'instant en UTC : `2026-10-14T02:31:05Z`. Toujours UTC : un fichier lu plus tard, sur
/// une autre machine ou après un changement d'heure, dit la même chose.
pub fn format_utc(unix_secs: u64) -> String {
    let secs_of_day = unix_secs % 86_400;
    format!(
        "{}T{:02}:{:02}:{:02}Z",
        day_stamp(unix_secs),
        secs_of_day / 3_600,
        secs_of_day % 3_600 / 60,
        secs_of_day % 60
    )
}

/// Durée écoulée depuis le début du direct : `+00:12:34`.
fn format_elapsed(secs: u64) -> String {
    format!(
        "+{:02}:{:02}:{:02}",
        secs / 3_600,
        secs % 3_600 / 60,
        secs % 60
    )
}

/// Ce que le journal retient d'un direct en cours.
#[derive(Debug, Default)]
pub struct StreamLog {
    /// Instant (secondes unix) du début du direct ; `None` hors direct.
    started_at: Option<u64>,
    last_dropped: i32,
    last_total: i32,
    /// Instant de la dernière ligne `images` écrite.
    last_written_at: u64,
}

impl StreamLog {
    pub fn new() -> Self {
        Self::default()
    }

    /// Reçoit un message du moteur ; rend la ligne à écrire, ou `None` s'il n'y a rien à
    /// dire. `settings` décrit les réglages d'encodage du direct (lu côté application) et
    /// n'est utilisé qu'au démarrage.
    pub fn on_message(&mut self, msg: &EngineMessage, now: u64, settings: &str) -> Option<String> {
        let stamp = format_utc(now);
        match msg {
            EngineMessage::Started => {
                self.started_at = Some(now);
                self.last_dropped = 0;
                self.last_total = 0;
                self.last_written_at = now;
                Some(format!("{stamp}  DEBUT   {settings}"))
            }
            EngineMessage::VideoEncoder { kind, hardware } => self.started_at.map(|_| {
                let hw = if *hardware { "oui" } else { "non" };
                format!("{stamp}  encodeur  {kind}  materiel={hw}")
            }),
            EngineMessage::Frames { dropped, total } => {
                let started = self.started_at?;
                let delta = dropped - self.last_dropped;
                let quiet = now.saturating_sub(self.last_written_at) < HEARTBEAT_SECS;
                self.last_total = *total;
                self.last_dropped = *dropped;
                if delta <= 0 && quiet {
                    return None;
                }
                self.last_written_at = now;
                Some(format!(
                    "{stamp}  {}  images  perdues={dropped} ({delta:+})  total={total}  taux={:.2} %",
                    format_elapsed(now.saturating_sub(started)),
                    drop_rate_percent(*dropped, *total)
                ))
            }
            EngineMessage::StreamStopped => {
                let started = self.started_at.take()?;
                Some(format!(
                    "{stamp}  {}  FIN     perdues={}  total={}  taux={:.2} %",
                    format_elapsed(now.saturating_sub(started)),
                    self.last_dropped,
                    self.last_total,
                    drop_rate_percent(self.last_dropped, self.last_total)
                ))
            }
            EngineMessage::Error { message } => {
                let started = self.started_at?;
                let short: String = message.chars().take(MAX_ERROR_CHARS).collect();
                Some(format!(
                    "{stamp}  {}  erreur  {short}",
                    format_elapsed(now.saturating_sub(started))
                ))
            }
            _ => None,
        }
    }
}

/// Les réglages d'encodage de CE direct, tels que l'application les enverra au moteur.
/// « auto » quand l'utilisateur n'a rien posé. Lecture seule, sans clé ni compte.
pub fn describe_encoding(app: &AppHandle) -> String {
    let bitrate =
        saved_bitrate_kbps(app).map_or_else(|| "auto".to_string(), |k| format!("{k} kb/s"));
    let composition = saved_composition(app).map_or_else(
        || "auto".to_string(),
        |c| format!("{}x{}@{}", c.width, c.height, c.fps),
    );
    let encoder = saved_encoder(app).map_or_else(|| "auto".to_string(), |e| format!("{e:?}"));
    format!("debit={bitrate}  sortie={composition}  encodeur={encoder}")
}

/// Ajoute une ligne au fichier du jour (`stream-AAAA-MM-JJ.log`) de `dir`. Une panne
/// d'écriture est signalée sur la console et jamais propagée : un journal ne doit pas
/// pouvoir gêner le direct qu'il observe.
pub fn append_line(dir: &Path, unix_secs: u64, line: &str) {
    let write = || -> std::io::Result<()> {
        std::fs::create_dir_all(dir)?;
        let path = dir.join(format!("stream-{}.log", day_stamp(unix_secs)));
        let mut file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)?;
        writeln!(file, "{line}")
    };
    if let Err(err) = write() {
        eprintln!("[stream-log] écriture impossible : {err}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const START: u64 = 1_791_945_065; // 2026-10-14T02:31:05Z

    fn frames(dropped: i32, total: i32) -> EngineMessage {
        EngineMessage::Frames { dropped, total }
    }

    #[test]
    fn should_append_lines_to_a_file_named_after_the_day() {
        let dir =
            std::env::temp_dir().join(format!("hikari-stream-log-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);

        append_line(&dir, START, "premiere ligne");
        append_line(&dir, START + 60, "seconde ligne");

        let content =
            std::fs::read_to_string(dir.join("stream-2026-10-14.log")).expect("fichier du jour");
        assert_eq!(content, "premiere ligne\nseconde ligne\n");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn should_never_panic_when_the_folder_cannot_be_written() {
        // Un chemin impossible (un fichier à la place du dossier) : le journal se tait, le
        // direct continue.
        let blocker =
            std::env::temp_dir().join(format!("hikari-stream-log-blocker-{}", std::process::id()));
        std::fs::write(&blocker, b"x").expect("fichier bloquant");

        append_line(&blocker.join("logs"), START, "ligne perdue");

        let _ = std::fs::remove_file(&blocker);
    }

    #[test]
    fn should_format_a_known_instant_in_utc() {
        assert_eq!(format_utc(START), "2026-10-14T02:31:05Z");
        assert_eq!(format_utc(0), "1970-01-01T00:00:00Z");
    }

    #[test]
    fn should_handle_the_end_of_february_and_a_leap_day() {
        assert_eq!(format_utc(1_772_323_199), "2026-02-28T23:59:59Z");
        assert_eq!(format_utc(1_709_208_000), "2024-02-29T12:00:00Z");
        assert_eq!(day_stamp(1_709_208_000), "2024-02-29");
    }

    #[test]
    fn should_compute_the_drop_rate_without_dividing_by_zero() {
        assert_eq!(drop_rate_percent(5, 0), 0.0);
        assert!((drop_rate_percent(12, 1_800) - 0.6667).abs() < 0.001);
    }

    #[test]
    fn should_write_the_encoding_settings_when_a_stream_starts() {
        let mut log = StreamLog::new();

        let line = log
            .on_message(&EngineMessage::Started, START, "720p60 nvenc 5000 kb/s")
            .expect("le début d'un direct se note");

        assert!(line.contains("DEBUT"));
        assert!(line.contains("720p60 nvenc 5000 kb/s"));
    }

    #[test]
    fn should_stay_silent_while_nothing_is_lost_and_no_heartbeat_is_due() {
        let mut log = StreamLog::new();
        log.on_message(&EngineMessage::Started, START, "");

        assert!(log.on_message(&frames(0, 120), START + 2, "").is_none());
        assert!(log.on_message(&frames(0, 240), START + 4, "").is_none());
    }

    #[test]
    fn should_write_a_line_as_soon_as_frames_are_lost() {
        let mut log = StreamLog::new();
        log.on_message(&EngineMessage::Started, START, "");
        log.on_message(&frames(0, 120), START + 2, "");

        let line = log
            .on_message(&frames(3, 240), START + 4, "")
            .expect("une perte se note");

        assert!(line.contains("perdues=3 (+3)"));
        assert!(line.contains("+00:00:04"));
    }

    #[test]
    fn should_write_a_heartbeat_line_when_everything_is_fine_for_a_while() {
        let mut log = StreamLog::new();
        log.on_message(&EngineMessage::Started, START, "");

        let line = log
            .on_message(&frames(0, 1_800), START + 30, "")
            .expect("un battement tous les 30 s montre que tout va bien");

        assert!(line.contains("perdues=0"));
    }

    #[test]
    fn should_ignore_frames_outside_a_stream() {
        let mut log = StreamLog::new();

        assert!(log.on_message(&frames(9, 100), START, "").is_none());
    }

    #[test]
    fn should_summarise_the_stream_when_it_stops_then_go_quiet_again() {
        let mut log = StreamLog::new();
        log.on_message(&EngineMessage::Started, START, "");
        log.on_message(&frames(12, 1_800), START + 600, "");

        let line = log
            .on_message(&EngineMessage::StreamStopped, START + 610, "")
            .expect("la fin d'un direct se note");

        assert!(line.contains("FIN"));
        assert!(line.contains("perdues=12"));
        assert!(line.contains("total=1800"));
        assert!(log
            .on_message(&frames(13, 1_900), START + 700, "")
            .is_none());
    }

    #[test]
    fn should_keep_engine_errors_only_during_a_stream_and_shorten_them() {
        let mut log = StreamLog::new();
        let error = EngineMessage::Error {
            message: "x".repeat(500),
        };
        assert!(log.on_message(&error, START, "").is_none());

        log.on_message(&EngineMessage::Started, START, "");
        let line = log
            .on_message(&error, START + 5, "")
            .expect("erreur en direct");

        assert!(line.contains("erreur"));
        assert!(line.len() < 300);
    }
}
