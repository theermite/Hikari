//! Isolated execution ("Let It Crash", CDC §4/§8): each automation's actions run on
//! their OWN tokio task. A panic inside one automation's action never propagates to
//! the caller, the live stream, or any other automation — it surfaces as a normal
//! `Err` on that automation's own `JoinHandle`.
//!
//! This module deliberately does NOT interpret `Action` — deciding what a
//! `SwitchScene` or `HttpRequest` actually DOES belongs to the app that consumes this
//! crate's `Decision` (B4/B6/...), never to the engine (ADR-008: automations are
//! data, the engine's job stops at the decision).

use tokio::task::JoinHandle;

use crate::model::Action;

/// How one automation's isolated execution ended.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ExecutionOutcome {
    /// Every action ran without panicking.
    Completed,
    /// An action panicked; the message is whatever `std::panic` captured, best-effort.
    Panicked(String),
}

/// Runs `actions` through `run_action` on an isolated blocking task (CDC §8: "une
/// action lente bloque la chaîne" — moving it off the caller's task means a slow or
/// panicking action never blocks/crashes the caller). One task per call, so one
/// automation's failure is structurally incapable of touching another's.
pub fn spawn_isolated<F>(actions: Vec<Action>, run_action: F) -> JoinHandle<ExecutionOutcome>
where
    F: Fn(Action) + Send + 'static,
{
    tokio::task::spawn_blocking(move || {
        for action in actions {
            run_action(action);
        }
        ExecutionOutcome::Completed
    })
}

/// Awaits `handle`, turning a task panic into `ExecutionOutcome::Panicked` instead of
/// letting the panic propagate to the awaiting caller (the actual Let-It-Crash
/// boundary: `tokio::task::JoinError` already contains the captured panic payload).
pub async fn await_isolated(handle: JoinHandle<ExecutionOutcome>) -> ExecutionOutcome {
    match handle.await {
        Ok(outcome) => outcome,
        Err(join_error) => ExecutionOutcome::Panicked(join_error.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn should_complete_when_actions_run_cleanly() {
        let actions = vec![Action::Wait { millis: 0 }];
        let handle = spawn_isolated(actions, |_action| {
            // No-op executor: this test proves isolation plumbing, not a real sink.
        });
        assert_eq!(await_isolated(handle).await, ExecutionOutcome::Completed);
    }

    #[tokio::test]
    async fn should_report_panic_without_crashing_caller_when_action_panics() {
        let actions = vec![Action::Wait { millis: 0 }];
        let handle = spawn_isolated(actions, |_action| {
            panic!("simulated action failure");
        });
        // The await itself must not panic — Let It Crash means THIS test function
        // keeps running and can assert on the outcome.
        let outcome = await_isolated(handle).await;
        assert!(matches!(outcome, ExecutionOutcome::Panicked(_)));
    }

    #[tokio::test]
    async fn should_isolate_one_panicking_automation_from_another() {
        let panicking = spawn_isolated(vec![Action::Wait { millis: 0 }], |_| {
            panic!("automation A explodes");
        });
        let healthy = spawn_isolated(vec![Action::Wait { millis: 0 }], |_| {
            // Runs to completion regardless of the other task's fate.
        });
        let (panicking_outcome, healthy_outcome) =
            tokio::join!(await_isolated(panicking), await_isolated(healthy));
        assert!(matches!(panicking_outcome, ExecutionOutcome::Panicked(_)));
        assert_eq!(healthy_outcome, ExecutionOutcome::Completed);
    }
}
