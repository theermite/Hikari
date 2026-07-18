//! Hikari automation engine (B-auto, PET §7ter).
//!
//! An automation is DATA — `{id, name, trigger, conditions[], actions[], active}` —
//! never executed code (ADR-008). The trigger is an attribute of that data, not a
//! different kind of automation (ADR-012): bouton | commande chat | événement |
//! minuteur, one mechanism. This crate is the single source of truth the local deck
//! (B4) and remote deck (B5) both consume (ADR-011) — zero duplicated logic on
//! either client.
//!
//! Module map:
//! - [`model`] — the data shapes (`Automation`, `Trigger`, `Condition`, `Action`).
//! - [`triggers`] — the one trigger-specific guard (chat command whitelist).
//! - [`engine`] — the pure evaluator: registration (cycle detection), decision.
//! - [`execution`] — isolated, per-automation task execution ("Let It Crash").

pub mod engine;
pub mod execution;
pub mod model;
pub mod triggers;

pub use engine::{AutomationEngine, Decision, EngineError, RefusalReason, MAX_SEQUENCE_DEPTH};
pub use execution::{await_isolated, spawn_isolated, ExecutionOutcome};
pub use model::{Action, Automation, AutomationId, Condition, ConditionError, Context, Trigger};
pub use triggers::{ChatCommandWhitelist, TriggerError};
