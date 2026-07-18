//! Property-based tests (anti-circular Layer 1, Quality.md) for the automation
//! engine. Two properties matter most for a Critical module: the evaluator is PURE
//! (same automation + same context always yields the same `Decision`), and the wire
//! model round-trips through JSON without loss — the shape B4/B5 will actually send
//! over the interface (ADR-011).

use std::collections::HashMap;

use hikari_automation::{Action, Automation, AutomationEngine, Condition, Context, Trigger};
use proptest::prelude::*;

/// Strategy building an arbitrary, always-safe automation `id`/`name` (bounded ASCII,
/// no control characters — the property under test is determinism, not encoding).
fn ident_strategy() -> impl Strategy<Value = String> {
    "[a-z][a-z0-9_-]{0,15}"
}

fn trigger_strategy() -> impl Strategy<Value = Trigger> {
    prop_oneof![
        Just(Trigger::Button),
        ident_strategy().prop_map(|command| Trigger::ChatCommand { command }),
        ident_strategy().prop_map(|event_name| Trigger::Event { event_name }),
        (1u64..3600).prop_map(|interval_secs| Trigger::Timer { interval_secs }),
    ]
}

fn condition_strategy() -> impl Strategy<Value = Condition> {
    prop_oneof![
        Just(Condition::Always),
        (ident_strategy(), ident_strategy())
            .prop_map(|(variable, value)| Condition::VariableEquals { variable, value }),
        ident_strategy().prop_map(|variable| Condition::VariableExists { variable }),
    ]
}

fn action_strategy() -> impl Strategy<Value = Action> {
    prop_oneof![
        ident_strategy().prop_map(|scene| Action::SwitchScene { scene }),
        (ident_strategy(), any::<bool>())
            .prop_map(|(source, visible)| Action::SetSourceVisibility { source, visible }),
        ident_strategy().prop_map(|message| Action::SendChatMessage { message }),
        ident_strategy().prop_map(|sound_id| Action::PlaySound { sound_id }),
        (0u64..5000).prop_map(|millis| Action::Wait { millis }),
    ]
}

fn context_strategy() -> impl Strategy<Value = Context> {
    prop::collection::hash_map(ident_strategy(), ident_strategy(), 0..4)
        .prop_map(|variables: HashMap<String, String>| Context { variables })
}

/// An automation with NO `RunAutomation` action, so it registers on its own without
/// needing any other automation to exist first (keeps the strategy simple; the cycle
/// graph itself is covered by the targeted unit tests in `engine.rs`).
fn leaf_automation_strategy() -> impl Strategy<Value = Automation> {
    (
        ident_strategy(),
        ident_strategy(),
        trigger_strategy(),
        prop::collection::vec(condition_strategy(), 0..3),
        prop::collection::vec(action_strategy(), 0..4),
        any::<bool>(),
    )
        .prop_map(|(id, name, trigger, conditions, actions, active)| Automation {
            id,
            name,
            trigger,
            conditions,
            actions,
            active,
        })
}

proptest! {
    #[test]
    fn should_decide_deterministically_when_same_inputs(
        automation in leaf_automation_strategy(),
        context in context_strategy(),
    ) {
        // ChatCommand needs its command whitelisted, or registration would (rightly)
        // fail — whitelist whatever command this run generated so registration never
        // fails for a reason unrelated to the property under test.
        let whitelist = match &automation.trigger {
            Trigger::ChatCommand { command } => {
                hikari_automation::ChatCommandWhitelist::new([command.clone()])
            }
            _ => hikari_automation::ChatCommandWhitelist::default(),
        };
        let mut engine = AutomationEngine::new(whitelist);
        let id = engine.register(automation).expect("leaf automation always registers");

        let first = engine.decide(&id, &context);
        let second = engine.decide(&id, &context);
        prop_assert_eq!(first, second, "same automation + same context must yield the same decision");
    }

    #[test]
    fn should_roundtrip_automation_when_serialized(automation in leaf_automation_strategy()) {
        let json = serde_json::to_string(&automation).expect("serializes");
        let parsed: Automation = serde_json::from_str(&json).expect("valid JSON must parse");
        prop_assert_eq!(parsed, automation);
    }
}
