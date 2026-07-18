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
use hikari_protocol::parse_engine_message;

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

/// Spawn the engine as a child process with piped stdout, or fail with context.
fn spawn_engine(engine: &PathBuf, args: &[String]) -> Result<Child> {
    Command::new(engine)
        .args(args)
        .stdout(Stdio::piped())
        .spawn()
        .with_context(|| format!("launching engine at {}", engine.display()))
}

/// Relay the engine's stdout line by line, parsing each as a protocol message. Unparsable
/// lines are reported as warnings — never swallowed.
fn relay_output(child: &mut Child) -> Result<()> {
    let stdout = child.stdout.take().context("engine stdout was not piped")?;
    for line in BufReader::new(stdout).lines() {
        let line = line.context("reading engine stdout")?;
        match parse_engine_message(&line) {
            Ok(msg) => eprintln!("[engine] {msg:?}"),
            Err(err) => eprintln!("[engine] WARN unparsable line {line:?} ({err})"),
        }
    }
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
    fn should_point_engine_path_at_neighbor_binary() {
        let path = engine_path().expect("engine path resolves");
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or_default();
        assert!(name.starts_with("hikari-engine"), "engine is the neighbor binary, got {name:?}");
        assert!(path.is_absolute(), "engine path must be absolute");
    }
}
