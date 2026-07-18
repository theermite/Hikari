//! Trigger-specific validation (ADR-012). The trigger is an attribute of the
//! automation, not a separate "kind" of object (see `model::Trigger`) — this module
//! holds only the ONE trigger-specific guard the CDC calls out: the chat command
//! whitelist (CDC §8 FMEA: "liste blanche des commandes exposées au chat, refus par
//! défaut").

use std::collections::HashSet;

use crate::model::Trigger;

/// A trigger failed registration-time validation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TriggerError {
    ChatCommandNotWhitelisted(String),
}

/// Closed list of chat commands allowed to trigger an automation. Empty by default —
/// a project wires its own commands explicitly; the engine never assumes a command is
/// safe just because a viewer typed it (fail-closed, CDC §8 FMEA).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ChatCommandWhitelist(HashSet<String>);

impl ChatCommandWhitelist {
    pub fn new(commands: impl IntoIterator<Item = String>) -> Self {
        Self(commands.into_iter().collect())
    }

    pub fn allows(&self, command: &str) -> bool {
        self.0.contains(command)
    }
}

/// Validates a trigger at registration time.
///
/// Only `ChatCommand` carries a guard today (the whitelist). `Button`/`Event`/`Timer`
/// are always valid triggers here — an unrecognized wire-level trigger `type` never
/// reaches this function at all: `serde`'s closed tagged enum on `Trigger` rejects it
/// during `Automation` deserialization first (`should_reject_unknown_trigger_type`,
/// covered in `tests/engine.rs` against the full registration path).
pub fn validate_trigger(
    trigger: &Trigger,
    whitelist: &ChatCommandWhitelist,
) -> Result<(), TriggerError> {
    if let Trigger::ChatCommand { command } = trigger {
        if !whitelist.allows(command) {
            return Err(TriggerError::ChatCommandNotWhitelisted(command.clone()));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_allow_button_trigger_when_no_whitelist_needed() {
        let whitelist = ChatCommandWhitelist::default();
        assert_eq!(validate_trigger(&Trigger::Button, &whitelist), Ok(()));
    }

    #[test]
    fn should_reject_chat_command_when_not_whitelisted() {
        let whitelist = ChatCommandWhitelist::new(["!hype".to_string()]);
        let trigger = Trigger::ChatCommand { command: "!ban".to_string() };
        assert_eq!(
            validate_trigger(&trigger, &whitelist),
            Err(TriggerError::ChatCommandNotWhitelisted("!ban".to_string()))
        );
    }

    #[test]
    fn should_allow_chat_command_when_whitelisted() {
        let whitelist = ChatCommandWhitelist::new(["!hype".to_string()]);
        let trigger = Trigger::ChatCommand { command: "!hype".to_string() };
        assert_eq!(validate_trigger(&trigger, &whitelist), Ok(()));
    }
}
