//! Pure automation engine (ADR-008/011/012).
//!
//! Registration validates the trigger and detects `RunAutomation` cycles up front:
//! the graph of who-calls-whom is known the moment the user hits save, so a loop is
//! refused THEN, never discovered live (CDC §8 FMEA: "automation qui boucle... l'app
//! figée en direct = la douleur Streamer.bot reproduite" — bug confirmed in their own
//! changelog v0.2.4, `docs/refs-concurrence/Analyse-Streamerbot-TouchPortal.md` §4).
//!
//! `decide` is the pure part: same automation + same context always yields the same
//! `Decision` (no I/O, no clock, no randomness) — the property under test in
//! `tests/proptest_engine.rs`.

use std::collections::{HashMap, HashSet};

use crate::model::{Action, Automation, AutomationId, Context, ConditionError};
use crate::triggers::{self, ChatCommandWhitelist, TriggerError};

/// Anti-loop ceiling: how many `RunAutomation` hops a single trigger may cross before
/// the engine refuses (CDC §8: "profondeur de séquence bornée"). A second, orthogonal
/// defense to cycle detection — cycle detection blocks the graph from ever containing
/// a loop; this bounds any accidentally very-deep (but acyclic) chain too.
pub const MAX_SEQUENCE_DEPTH: usize = 8;

/// Registration or lookup failed.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EngineError {
    UnknownAutomation(AutomationId),
    DuplicateId(AutomationId),
    Trigger(TriggerError),
    CycleDetected(AutomationId),
    InvalidJson(String),
}

/// The outcome of evaluating one automation against a context — a CLOSED enum, so a
/// caller can never mistake "refused" for "ran" (CDC §8: refusal is fail-closed by
/// construction, not by convention).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Decision {
    Run(Vec<Action>),
    Refused(RefusalReason),
}

/// Why an otherwise-valid, registered automation did not run.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RefusalReason {
    Inactive,
    ConditionFalse,
    ConditionUnevaluable { variable: String },
    SequenceDepthExceeded,
    /// A `RunAutomation` action pointed at an id that is no longer registered
    /// (defensive: cycle detection assumes the graph is stable, this guards the case
    /// where it was not — Quality.md "errors are data", never a panic).
    ReferencedAutomationMissing(AutomationId),
}

/// Registered automations plus the one trigger-specific guard (chat whitelist).
#[derive(Debug, Default)]
pub struct AutomationEngine {
    automations: HashMap<AutomationId, Automation>,
    chat_whitelist: ChatCommandWhitelist,
}

impl AutomationEngine {
    pub fn new(chat_whitelist: ChatCommandWhitelist) -> Self {
        Self { automations: HashMap::new(), chat_whitelist }
    }

    /// Parses one automation from a JSON line and registers it. An unrecognized
    /// `trigger.type` (or any other structurally invalid input) is rejected here,
    /// before it ever reaches trigger/cycle validation — `serde`'s tagged enums are
    /// closed sets (`should_reject_unknown_trigger_type`).
    pub fn register_from_json(&mut self, json: &str) -> Result<AutomationId, EngineError> {
        let automation: Automation =
            serde_json::from_str(json).map_err(|e| EngineError::InvalidJson(e.to_string()))?;
        self.register(automation)
    }

    /// Registers an automation: rejects a duplicate id, an unwhitelisted chat
    /// command, and a `RunAutomation` cycle — in that order, fail-closed on the
    /// first violation.
    pub fn register(&mut self, automation: Automation) -> Result<AutomationId, EngineError> {
        if self.automations.contains_key(&automation.id) {
            return Err(EngineError::DuplicateId(automation.id));
        }
        triggers::validate_trigger(&automation.trigger, &self.chat_whitelist)
            .map_err(EngineError::Trigger)?;
        self.assert_no_cycle(&automation)?;
        let id = automation.id.clone();
        self.automations.insert(id.clone(), automation);
        Ok(id)
    }

    /// DFS over `RunAutomation` edges starting at the candidate's own actions. The
    /// whole graph is known in advance (every OTHER automation is already
    /// registered), so a path back to the candidate's own id proves a cycle before
    /// it is ever stored.
    fn assert_no_cycle(&self, candidate: &Automation) -> Result<(), EngineError> {
        let mut visited = HashSet::new();
        let mut stack: Vec<AutomationId> =
            candidate.actions.iter().filter_map(Action::referenced_automation).cloned().collect();
        while let Some(next_id) = stack.pop() {
            if next_id == candidate.id {
                return Err(EngineError::CycleDetected(candidate.id.clone()));
            }
            if !visited.insert(next_id.clone()) {
                continue; // already walked this node on another path — no need to redo it.
            }
            if let Some(next) = self.automations.get(&next_id) {
                stack.extend(
                    next.actions.iter().filter_map(Action::referenced_automation).cloned(),
                );
            }
        }
        Ok(())
    }

    /// Pure decision for one automation against one context (see module doc).
    pub fn decide(&self, id: &AutomationId, context: &Context) -> Result<Decision, EngineError> {
        let automation =
            self.automations.get(id).ok_or_else(|| EngineError::UnknownAutomation(id.clone()))?;
        if !automation.active {
            return Ok(Decision::Refused(RefusalReason::Inactive));
        }
        if let Some(refusal) = first_failing_condition(automation, context) {
            return Ok(Decision::Refused(refusal));
        }
        Ok(match self.expand_actions(&automation.actions, 0) {
            Ok(actions) => Decision::Run(actions),
            Err(refusal) => Decision::Refused(refusal),
        })
    }

    /// Expands nested `RunAutomation` actions into a flat, ordered sequence,
    /// depth-bounded (CDC §8 anti-loop ceiling). A missing referenced automation
    /// refuses closed rather than silently dropping the step.
    fn expand_actions(&self, actions: &[Action], depth: usize) -> Result<Vec<Action>, RefusalReason> {
        if depth > MAX_SEQUENCE_DEPTH {
            return Err(RefusalReason::SequenceDepthExceeded);
        }
        let mut expanded = Vec::with_capacity(actions.len());
        for action in actions {
            match action.referenced_automation() {
                Some(referenced_id) => {
                    let referenced = self
                        .automations
                        .get(referenced_id)
                        .ok_or_else(|| RefusalReason::ReferencedAutomationMissing(referenced_id.clone()))?;
                    expanded.extend(self.expand_actions(&referenced.actions, depth + 1)?);
                }
                None => expanded.push(action.clone()),
            }
        }
        Ok(expanded)
    }

    /// Automations eligible for deck assignment: button-triggered ones only
    /// (ADR-012). Single query point — B4 never re-derives the rule itself.
    pub fn deck_eligible_automations(&self) -> Vec<&Automation> {
        self.automations.values().filter(|a| a.trigger.is_deck_eligible()).collect()
    }
}

/// Evaluates every condition in order against `context`; the first `false` or
/// unevaluable result closes the gate. `None` means every condition passed — a free
/// function (not a method) so it stays a pure, independently testable unit, and to
/// keep `AutomationEngine::decide` under the 30-line ceiling (Quality.md).
fn first_failing_condition(automation: &Automation, context: &Context) -> Option<RefusalReason> {
    for condition in &automation.conditions {
        match condition.evaluate(context) {
            Ok(true) => {}
            Ok(false) => return Some(RefusalReason::ConditionFalse),
            Err(ConditionError::Unevaluable { variable }) => {
                return Some(RefusalReason::ConditionUnevaluable { variable });
            }
        }
    }
    None
}

// Behavioral tests for this module live in `tests/engine.rs` (integration tests
// against the public API only) — kept out of this file to stay under the 300-line
// file guideline (`.claude/rules/Quality.md`). They cover the 5 PET-mandated
// assertions verbatim plus registration edge cases (duplicate id, self-cycle, unknown
// automation id, max sequence depth).
