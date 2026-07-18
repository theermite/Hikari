//! Integration tests for `AutomationEngine`, against the crate's public API only
//! (kept out of `src/engine.rs` to stay under the 300-line file guideline,
//! `.claude/rules/Quality.md`). Covers the 5 PET-mandated assertions verbatim
//! (`docs/PET.md` §"B-auto"): `should_run_action_when_condition_true` ·
//! `should_refuse_when_condition_unevaluable` · `should_reject_cycle_at_save` ·
//! `should_reject_unknown_trigger_type` · `should_never_expose_event_trigger_as_deck_key`.

use hikari_automation::{
    Action, Automation, AutomationEngine, Condition, Context, Decision, EngineError,
    RefusalReason, Trigger, MAX_SEQUENCE_DEPTH,
};

fn button_automation(id: &str, active: bool) -> Automation {
    Automation {
        id: id.to_string(),
        name: "test".to_string(),
        trigger: Trigger::Button,
        conditions: vec![],
        actions: vec![Action::SwitchScene { scene: "Just Chatting".to_string() }],
        active,
    }
}

#[test]
fn should_run_action_when_condition_true() {
    let mut engine = AutomationEngine::default();
    engine.register(button_automation("clip-hype", true)).expect("registers cleanly");
    let decision = engine.decide(&"clip-hype".to_string(), &Context::new()).expect("known id");
    assert_eq!(
        decision,
        Decision::Run(vec![Action::SwitchScene { scene: "Just Chatting".to_string() }])
    );
}

#[test]
fn should_refuse_when_inactive() {
    let mut engine = AutomationEngine::default();
    engine.register(button_automation("disabled", false)).expect("registers cleanly");
    let decision = engine.decide(&"disabled".to_string(), &Context::new()).expect("known id");
    assert_eq!(decision, Decision::Refused(RefusalReason::Inactive));
}

#[test]
fn should_refuse_when_condition_unevaluable() {
    let mut automation = button_automation("sub-only", true);
    automation.conditions =
        vec![Condition::VariableEquals { variable: "sub_tier".to_string(), value: "3".to_string() }];
    let mut engine = AutomationEngine::default();
    engine.register(automation).expect("registers cleanly");
    // The context never deposited `sub_tier` — closed refusal, never a silent run.
    let decision = engine.decide(&"sub-only".to_string(), &Context::new()).expect("known id");
    assert_eq!(
        decision,
        Decision::Refused(RefusalReason::ConditionUnevaluable { variable: "sub_tier".to_string() })
    );
}

#[test]
fn should_reject_cycle_at_save() {
    let mut engine = AutomationEngine::default();
    let mut a = button_automation("a", true);
    a.actions = vec![Action::RunAutomation { automation_id: "b".to_string() }];
    let mut b = button_automation("b", true);
    b.actions = vec![Action::RunAutomation { automation_id: "a".to_string() }];
    engine.register(a).expect("a registers before the cycle closes");
    let result = engine.register(b);
    assert_eq!(result, Err(EngineError::CycleDetected("b".to_string())));
}

#[test]
fn should_reject_self_referencing_cycle_at_save() {
    let mut engine = AutomationEngine::default();
    let mut looped = button_automation("loop", true);
    looped.actions = vec![Action::RunAutomation { automation_id: "loop".to_string() }];
    assert_eq!(engine.register(looped), Err(EngineError::CycleDetected("loop".to_string())));
}

#[test]
fn should_reject_unknown_trigger_type() {
    let mut engine = AutomationEngine::default();
    let json = r#"{
        "id": "mystery",
        "name": "mystery",
        "trigger": {"type": "webhook"},
        "conditions": [],
        "actions": [],
        "active": true
    }"#;
    let result = engine.register_from_json(json);
    assert!(matches!(result, Err(EngineError::InvalidJson(_))));
}

#[test]
fn should_reject_duplicate_id_at_save() {
    let mut engine = AutomationEngine::default();
    engine.register(button_automation("dup", true)).expect("first registers");
    let result = engine.register(button_automation("dup", true));
    assert_eq!(result, Err(EngineError::DuplicateId("dup".to_string())));
}

#[test]
fn should_reject_sequence_beyond_max_depth() {
    let mut engine = AutomationEngine::default();
    // Straight chain of MAX_SEQUENCE_DEPTH + 2 automations, each calling the next —
    // acyclic, so registration succeeds every time, but the decision must still
    // refuse once the anti-loop ceiling is crossed (CDC §8).
    let chain_len = MAX_SEQUENCE_DEPTH + 2;
    for i in (0..chain_len).rev() {
        let mut step = button_automation(&format!("step-{i}"), true);
        if i + 1 < chain_len {
            step.actions = vec![Action::RunAutomation { automation_id: format!("step-{}", i + 1) }];
        }
        engine.register(step).expect("acyclic chain registers");
    }
    let decision = engine.decide(&"step-0".to_string(), &Context::new()).expect("known id");
    assert_eq!(decision, Decision::Refused(RefusalReason::SequenceDepthExceeded));
}

#[test]
fn should_never_expose_event_trigger_as_deck_key() {
    let mut engine = AutomationEngine::default();
    engine.register(button_automation("deck-worthy", true)).expect("registers cleanly");
    let mut event_automation = button_automation("silent-follow", true);
    event_automation.trigger = Trigger::Event { event_name: "follow".to_string() };
    engine.register(event_automation).expect("registers cleanly");
    let deck_ids: Vec<&str> = engine.deck_eligible_automations().iter().map(|a| a.id.as_str()).collect();
    assert_eq!(deck_ids, vec!["deck-worthy"]);
}

#[test]
fn should_refuse_when_unknown_automation_id() {
    let engine = AutomationEngine::default();
    let result = engine.decide(&"ghost".to_string(), &Context::new());
    assert_eq!(result, Err(EngineError::UnknownAutomation("ghost".to_string())));
}
