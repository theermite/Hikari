//! Data model for automations (ADR-008): an automation is **data**, never executed
//! code. The shape mirrors the real Streamer.bot `actions.json` schema, verified by
//! reverse-engineering a production install (`docs/refs-concurrence/
//! Analyse-Streamerbot-TouchPortal.md` §1) — `{id, name, trigger, conditions, actions,
//! active}` is the leader's proven model, not a guess.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// Stable identifier of an automation, chosen by the caller (deck/UI) at creation —
/// matches the real `actions.json` `id` field.
pub type AutomationId = String;

/// What fires an automation. ADR-012: the trigger is an **attribute** of the
/// automation, not a different kind of object — one model, not four.
///
/// `#[serde(tag = "type")]` makes this a CLOSED set on the wire: an unrecognized
/// `type` value fails deserialization instead of being silently ignored (Quality.md
/// "Errors are data" — a silently-dropped unknown trigger would be a defect hiding as
/// a no-op).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Trigger {
    /// A deck button press — the button IS the trigger.
    Button,
    /// A chat command, gated by the engine's chat whitelist (`triggers.rs`).
    ChatCommand { command: String },
    /// A platform event (follow, sub, raid, ...). Fires unattended.
    Event { event_name: String },
    /// A recurring timer. Fires unattended.
    Timer { interval_secs: u64 },
}

impl Trigger {
    /// ADR-012's one rule: only a button trigger IS a deck key. Every other trigger
    /// stays off the deck by default. Single source of truth so B4 never re-derives
    /// this rule on its own (the historical bug this guards against: an automation
    /// silently appearing where nothing should have triggered it).
    pub fn is_deck_eligible(&self) -> bool {
        matches!(self, Trigger::Button)
    }
}

/// A guard evaluated against the trigger's deposited arguments before the actions run.
/// Closed set (`#[serde(tag = "type")]`), same reasoning as `Trigger`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Condition {
    /// Always true — the automation has no real guard (e.g. a plain manual button).
    Always,
    /// True only when `variable` is present in the context AND equals `value`.
    /// Unevaluable (see `evaluate`) when `variable` is absent — CDC §8 FMEA:
    /// "variable absente au moment d'évaluer une condition" must never resolve to
    /// a silent `true`.
    VariableEquals { variable: String, value: String },
    /// True when `variable` is present in the context, false otherwise. Always
    /// evaluable — existence is a well-defined question even when the variable is
    /// missing, unlike `VariableEquals`.
    VariableExists { variable: String },
}

/// A condition could not be evaluated — CDC §8: this must close the gate, never open
/// it (fail closed, not fail open).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConditionError {
    Unevaluable { variable: String },
}

impl Condition {
    /// Pure evaluation: same condition + same context always yields the same result
    /// (property under test in `tests/proptest_engine.rs`).
    pub fn evaluate(&self, context: &Context) -> Result<bool, ConditionError> {
        match self {
            Condition::Always => Ok(true),
            Condition::VariableExists { variable } => {
                Ok(context.variables.contains_key(variable))
            }
            Condition::VariableEquals { variable, value } => {
                match context.variables.get(variable) {
                    Some(current) => Ok(current == value),
                    None => Err(ConditionError::Unevaluable { variable: variable.clone() }),
                }
            }
        }
    }
}

/// The closed palette of actions an automation may take. Every variant is DATA — the
/// engine never interprets a string as code (ADR-008). Side effects (actually
/// switching a scene, posting to chat, ...) are performed by the app that consumes
/// this crate's `Decision`, never by the engine itself.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum Action {
    SwitchScene { scene: String },
    SetSourceVisibility { source: String, visible: bool },
    SendChatMessage { message: String },
    PlaySound { sound_id: String },
    /// CDC §8 FMEA: the path is a value chosen by the user (a file picker, at the UI
    /// layer) — the engine only carries it, it never builds one from an event.
    LaunchApplication { path: String },
    /// CDC §8 FMEA: the target is a value the user typed explicitly — the engine
    /// never derives it from a chat message or injects a token into it.
    HttpRequest { url: String },
    /// Chains to another automation's actions (sequencing). This is the ONLY
    /// variant that can create a cycle — `AutomationEngine::assert_no_cycle` walks
    /// exactly these edges.
    RunAutomation { automation_id: AutomationId },
    Wait { millis: u64 },
}

impl Action {
    /// The automation this action references, if any — the cycle graph's edges are
    /// exactly the `RunAutomation` actions; every other variant is a leaf.
    pub fn referenced_automation(&self) -> Option<&AutomationId> {
        match self {
            Action::RunAutomation { automation_id } => Some(automation_id),
            _ => None,
        }
    }
}

/// `{id, name, trigger, conditions[], actions[], active}` — the model proven by
/// Streamer.bot's real `actions.json` (see module doc).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Automation {
    pub id: AutomationId,
    pub name: String,
    pub trigger: Trigger,
    #[serde(default)]
    pub conditions: Vec<Condition>,
    #[serde(default)]
    pub actions: Vec<Action>,
    pub active: bool,
}

/// Arguments deposited by whatever fired the trigger (deck button, chat command,
/// event, timer). The automation reads these but never learns WHO deposited them —
/// the proven Streamer.bot model (`refs-concurrence/...` §2): "l'action ignore qui
/// l'a déclenchée".
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Context {
    pub variables: HashMap<String, String>,
}

impl Context {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_variable(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.variables.insert(key.into(), value.into());
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_evaluate_true_when_always() {
        let context = Context::new();
        assert_eq!(Condition::Always.evaluate(&context), Ok(true));
    }

    #[test]
    fn should_refuse_when_condition_unevaluable() {
        // The variable was never deposited — the engine must close the gate, not
        // assume a default (CDC §8 FMEA).
        let context = Context::new();
        let condition = Condition::VariableEquals {
            variable: "sub_tier".to_string(),
            value: "3".to_string(),
        };
        assert_eq!(
            condition.evaluate(&context),
            Err(ConditionError::Unevaluable { variable: "sub_tier".to_string() })
        );
    }

    #[test]
    fn should_evaluate_false_when_variable_exists_but_missing() {
        let context = Context::new();
        let condition = Condition::VariableExists { variable: "raid_from".to_string() };
        // Existence is always evaluable, unlike equality — never an error.
        assert_eq!(condition.evaluate(&context), Ok(false));
    }

    #[test]
    fn should_never_expose_event_trigger_as_deck_key() {
        // ADR-012, the Beyoncé-rule test named in the PET verbatim.
        let event = Trigger::Event { event_name: "follow".to_string() };
        assert!(!event.is_deck_eligible());
        let timer = Trigger::Timer { interval_secs: 60 };
        assert!(!timer.is_deck_eligible());
        let chat = Trigger::ChatCommand { command: "!hype".to_string() };
        assert!(!chat.is_deck_eligible());
        let button = Trigger::Button;
        assert!(button.is_deck_eligible());
    }

    #[test]
    fn should_find_referenced_automation_when_run_automation_action() {
        let action = Action::RunAutomation { automation_id: "hype-train".to_string() };
        assert_eq!(action.referenced_automation(), Some(&"hype-train".to_string()));
        let leaf = Action::Wait { millis: 500 };
        assert_eq!(leaf.referenced_automation(), None);
    }
}
