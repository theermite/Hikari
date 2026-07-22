//! Engine bridge — the controller side of the engine process (ADR-013).
//!
//! The Tauri app supervises the engine as a SEPARATE child process launched BY PATH,
//! never linked in. If the engine dies without finishing, the app survives, relaunches
//! it once, and SAYS so — a silent "ok" would be the real defect (B0.0 lesson).
//!
//! The relaunch policy is a PURE function (`decide_next`) so it is unit-tested without a
//! real process; the actual spawn/relay is a thin impure shell around it.

use std::env;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, ExitStatus, Stdio};

use anyhow::{Context, Result, bail};
use hikari_protocol::{CameraDevice, EngineMessage, parse_engine_message};

/// Maximum number of automatic relaunches before the controller gives up (B0.0 policy).
pub const MAX_RELAUNCH: usize = 1;

/// What the supervisor should do after the engine process exits — the pure decision.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SupervisorAction {
    /// The engine finished normally (exit 0). Nothing more to do.
    Done,
    /// The engine died without finishing; relaunch it (1-based attempt number).
    Relaunch { attempt: usize },
    /// The engine died and all relaunches are exhausted; stop and report.
    GiveUp,
}

/// Decide the next supervisor action from the engine's exit and the relaunch budget.
///
/// Pure and total: no I/O, no process. This is the logic proven by unit tests.
pub fn decide_next(exited_success: bool, relaunched: usize, max_relaunch: usize) -> SupervisorAction {
    if exited_success {
        return SupervisorAction::Done;
    }
    if relaunched < max_relaunch {
        return SupervisorAction::Relaunch { attempt: relaunched + 1 };
    }
    SupervisorAction::GiveUp
}

/// Absolute path of the engine binary — the neighbor of the controller in the same
/// `target/<profile>/` directory (ADR-013: launched by path, never linked).
pub fn engine_path() -> Result<PathBuf> {
    let exe = env::current_exe().context("resolving current executable path")?;
    let dir = exe.parent().context("resolving executable directory")?;
    let name = if cfg!(windows) { "hikari-engine.exe" } else { "hikari-engine" };
    Ok(dir.join(name))
}

/// Scans one-shot engine stdout for the `Encoders` message (B9 pré-vol, option A: a
/// standalone detection pass, never the continuous supervised process — that wiring stays
/// separate debt, see PET B1 "Dette restante"). Pure: no process, no libobs — testable
/// headless like `relay_reader`'s parsing.
fn extract_encoders(stdout: &str) -> Option<Vec<String>> {
    stdout.lines().find_map(|line| match parse_engine_message(line) {
        Ok(EngineMessage::Encoders { available }) => Some(available),
        _ => None,
    })
}

/// Runs the engine once in one-shot detection mode (`--detect-encoders`, never the
/// continuous supervised loop) and returns the encoder list it reported. Real libobs
/// process — integration-only, same regime as `supervise` (`extract_encoders` above
/// carries the part unit-testable without it).
pub fn run_detect_encoders() -> Result<Vec<String>> {
    let engine = engine_path()?;
    let output = Command::new(&engine)
        .arg("--detect-encoders")
        .output()
        .with_context(|| format!("launching engine at {}", engine.display()))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    extract_encoders(&stdout).context("engine did not report any encoders")
}

/// Scans one-shot engine stdout for the `Cameras` message (B-cam tranche 1, same option-A
/// shape as `extract_encoders`). Pure: no process, no libobs — testable headless.
fn extract_cameras(stdout: &str) -> Option<Vec<CameraDevice>> {
    stdout.lines().find_map(|line| match parse_engine_message(line) {
        Ok(EngineMessage::Cameras { devices }) => Some(devices),
        _ => None,
    })
}

/// Runs the engine once in one-shot detection mode (`--detect-cameras`) and returns the
/// camera devices it reported. Real libobs process — integration-only, same regime as
/// `run_detect_encoders`.
pub fn run_detect_cameras() -> Result<Vec<CameraDevice>> {
    let engine = engine_path()?;
    let output = Command::new(&engine)
        .arg("--detect-cameras")
        .output()
        .with_context(|| format!("launching engine at {}", engine.display()))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    extract_cameras(&stdout).context("engine did not report any cameras")
}

/// Spawn the engine as a child process with piped stdout, or fail with context.
fn spawn_engine(engine: &PathBuf, args: &[String]) -> Result<Child> {
    Command::new(engine)
        .args(args)
        .stdout(Stdio::piped())
        .spawn()
        .with_context(|| format!("launching engine at {}", engine.display()))
}

/// Relay engine stdout line by line; return how many well-formed protocol messages were
/// relayed. A read error on a single line (e.g. non-UTF8 output from the native libobs) is
/// logged and SKIPPED, never propagated: an I/O hiccup must not bypass the relaunch policy
/// (the engine's exit status from `child.wait()` is what drives supervision). Unparsable
/// lines are likewise reported, never swallowed.
fn relay_reader<R: BufRead>(reader: R) -> usize {
    let mut relayed = 0usize;
    for line in reader.lines() {
        match line {
            Ok(line) => match parse_engine_message(&line) {
                Ok(msg) => {
                    eprintln!("[engine] {msg:?}");
                    relayed += 1;
                }
                Err(err) => eprintln!("[engine] WARN unparsable line {line:?} ({err})"),
            },
            Err(err) => eprintln!("[engine] WARN dropped unreadable stdout line ({err})"),
        }
    }
    relayed
}

/// Take the child's piped stdout and relay it. Fails only on a missing pipe (a setup error
/// the caller must know about), never on stdout content — so supervision always reaches
/// `child.wait()` and the relaunch decision.
fn relay_output(child: &mut Child) -> Result<()> {
    let stdout = child.stdout.take().context("engine stdout was not piped")?;
    relay_reader(BufReader::new(stdout));
    Ok(())
}

/// Run the engine once: spawn, relay its output, and wait for its exit status.
fn run_engine_once(engine: &PathBuf, args: &[String]) -> Result<ExitStatus> {
    let mut child = spawn_engine(engine, args)?;
    relay_output(&mut child)?;
    child.wait().context("waiting for engine exit")
}

/// Supervise the engine: launch it as a separate process, and on death relaunch it up to
/// `MAX_RELAUNCH` times, announcing every transition. Returns `Ok` when it finishes
/// normally, `Err` when it dies with relaunches exhausted.
pub fn supervise(args: &[String]) -> Result<()> {
    let engine = engine_path()?;
    let mut relaunched = 0usize;
    loop {
        eprintln!("[controller] launching engine (separate process): {}", engine.display());
        let status = run_engine_once(&engine, args)?;
        match decide_next(status.success(), relaunched, MAX_RELAUNCH) {
            SupervisorAction::Done => {
                eprintln!("[controller] engine finished normally ({status})");
                return Ok(());
            }
            SupervisorAction::Relaunch { attempt } => {
                relaunched = attempt;
                eprintln!("[controller] /!\\ engine died ({status}) — controller SURVIVED, isolated relaunch {attempt}/{MAX_RELAUNCH}");
            }
            SupervisorAction::GiveUp => {
                bail!("engine died and relaunches are exhausted");
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn should_keep_relaying_when_a_stdout_line_is_not_utf8() {
        // A non-UTF8 byte on the engine's stdout must NOT abort supervision — otherwise a
        // native libobs log line would bypass the relaunch policy (ADR-013). The bad line
        // is skipped; the valid protocol messages still relay.
        let data: &[u8] = b"{\"type\":\"ready\"}\n\xff\xfe\n{\"type\":\"stopped\"}\n";
        let relayed = relay_reader(Cursor::new(data));
        assert_eq!(relayed, 2, "non-UTF8 line skipped, both valid messages still relayed");
    }

    #[test]
    fn should_report_unparsable_line_without_counting_it() {
        // A well-formed-but-unknown line is reported, not relayed, and never panics.
        let data: &[u8] = b"{\"type\":\"ready\"}\nnot json at all\n{\"type\":\"nope\"}\n";
        let relayed = relay_reader(Cursor::new(data));
        assert_eq!(relayed, 1, "only the valid `ready` message is relayed");
    }

    #[test]
    fn should_finish_when_engine_exits_successfully() {
        assert_eq!(decide_next(true, 0, MAX_RELAUNCH), SupervisorAction::Done);
        assert_eq!(decide_next(true, 5, MAX_RELAUNCH), SupervisorAction::Done);
    }

    #[test]
    fn should_relaunch_engine_when_it_dies() {
        // First death, budget available -> relaunch attempt 1.
        assert_eq!(
            decide_next(false, 0, MAX_RELAUNCH),
            SupervisorAction::Relaunch { attempt: 1 }
        );
    }

    #[test]
    fn should_give_up_when_relaunches_exhausted() {
        // Second death after one relaunch -> give up (never loop forever).
        assert_eq!(decide_next(false, 1, MAX_RELAUNCH), SupervisorAction::GiveUp);
        assert_eq!(decide_next(false, 2, MAX_RELAUNCH), SupervisorAction::GiveUp);
    }

    #[test]
    fn should_extract_encoders_from_one_shot_stdout() {
        let stdout = "{\"type\":\"encoders\",\"available\":[\"OBS_NVENC_H264_TEX\",\"OBS_X264\"]}\n";
        let encoders = extract_encoders(stdout).expect("encoders line present");
        assert_eq!(encoders, vec!["OBS_NVENC_H264_TEX".to_string(), "OBS_X264".to_string()]);
    }

    #[test]
    fn should_find_encoders_among_other_lines() {
        // A one-shot run may emit an error or unrelated line before/after `Encoders` —
        // the scan must not assume it's the first or only line.
        let stdout = "{\"type\":\"ready\"}\n{\"type\":\"encoders\",\"available\":[\"OBS_X264\"]}\n";
        assert_eq!(extract_encoders(stdout), Some(vec!["OBS_X264".to_string()]));
    }

    #[test]
    fn should_return_none_when_no_encoders_message_present() {
        let stdout = "{\"type\":\"ready\"}\n{\"type\":\"stopped\"}\n";
        assert_eq!(extract_encoders(stdout), None);
    }

    #[test]
    fn should_extract_cameras_from_one_shot_stdout() {
        let stdout = "{\"type\":\"cameras\",\"devices\":[{\"name\":\"Webcam HD\",\"device_id\":\"Webcam HD:usb#vid_0000\"}]}\n";
        let devices = extract_cameras(stdout).expect("cameras line present");
        assert_eq!(
            devices,
            vec![CameraDevice {
                name: "Webcam HD".to_string(),
                device_id: "Webcam HD:usb#vid_0000".to_string(),
            }]
        );
    }

    #[test]
    fn should_return_none_when_no_cameras_message_present() {
        let stdout = "{\"type\":\"ready\"}\n{\"type\":\"stopped\"}\n";
        assert_eq!(extract_cameras(stdout), None);
    }

    #[test]
    fn should_point_engine_path_at_neighbor_binary() {
        let path = engine_path().expect("engine path resolves");
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or_default();
        assert!(name.starts_with("hikari-engine"), "engine is the neighbor binary, got {name:?}");
        assert!(path.is_absolute(), "engine path must be absolute");
    }
}
