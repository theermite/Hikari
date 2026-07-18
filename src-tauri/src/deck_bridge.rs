//! Deck bridge (B4, PET §7ter) — the local deck is a CLIENT of the automation engine
//! (ADR-011), never a second brain: it never re-derives which automations belong on a
//! key, it only calls `AutomationEngine::deck_eligible_automations()` (ADR-012 lives
//! in `hikari_automation::model::Trigger::is_deck_eligible`, already proven by
//! `should_never_expose_event_trigger_as_deck_key`). This module performs ZERO network
//! I/O — every function here only touches the in-process `AutomationEngine`, so the
//! deck works identically with the machine offline (CDC §13 anti-pattern #4).
//!
//! Interpreting WHAT an `Action` does (switch a scene, post to chat, ...) is explicitly
//! out of `hikari-automation`'s scope (see its `execution` module doc) and out of THIS
//! brick's scope too: those effects belong to the bricks that own each subsystem
//! (scenes, chat, audio — none wired yet). `deck_sink` is an honest placeholder that
//! runs the isolated-execution plumbing without claiming a live effect it cannot
//! deliver yet (Dignity.md: never a button that silently pretends to work).

use std::sync::Mutex;

use hikari_automation::{Action, Automation, AutomationEngine, Context, Decision};
use tauri::State;

/// One assignable deck key: a button-triggered automation exposed by the engine. B4
/// delivers this ONE fully end-to-end-wired kind of key (PET roadmap row "Lien
/// automation ↔ deck"); the mockup's other 3 taxonomy slots (state toggle, read-only
/// value, board switch) each depend on a subsystem brick not built yet and are left for
/// those bricks to wire — showing them as working today would be exactly the silent
/// fake button Dignity.md forbids.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct DeckKey {
    pub id: String,
    pub label: String,
}

/// What happened when a key was pressed — mirrors the engine's own closed `Decision`
/// so the frontend can distinguish "ran" from "refused" instead of guessing from a bool.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum DeckTriggerOutcome {
    Dispatched,
    Refused { reason: String },
}

/// A key press that could not even reach a decision (unknown id, malformed engine
/// state). Distinct from `Refused`, which IS a valid, expected engine answer.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct DeckError(pub String);

/// Shared engine instance, held for the app's lifetime. Starts EMPTY: automation
/// authoring (the "Automations" screen) is a separate, not-yet-built brick — an empty
/// deck at first launch is an honest state, not a bug (mirrors `Sidebar`'s "bientôt"
/// treatment of screens that don't exist yet).
#[derive(Default)]
pub struct DeckState(pub Mutex<AutomationEngine>);

/// Placeholder action sink (see module doc): proves the decide → isolated-execution
/// path runs end to end without claiming a real side effect. Never touches the network
/// or any OS resource — this is exactly what keeps the deck's trigger path offline-safe.
fn deck_sink(_action: Action) {
    // Intentionally empty: real interpretation is wired brick by brick as the owning
    // subsystem lands (scenes, chat, audio, ...). See module doc.
}

/// Deck-eligible automations as deck keys — thin `Automation` -> `DeckKey` projection,
/// split out of the Tauri command so it is unit-testable without a Tauri runtime.
pub fn list_deck_keys(engine: &AutomationEngine) -> Vec<DeckKey> {
    engine.deck_eligible_automations().into_iter().map(deck_key_of).collect()
}

fn deck_key_of(automation: &Automation) -> DeckKey {
    DeckKey { id: automation.id.clone(), label: automation.name.clone() }
}

/// Core dispatch: decide, then spawn isolated execution WITHOUT awaiting it. The <100ms
/// budget (PET B4 acceptance criterion) covers decision + dispatch only — an action's
/// own duration (e.g. `Wait{millis:5000}`) must never make the button itself feel slow.
pub fn trigger_key(engine: &AutomationEngine, id: &str) -> Result<DeckTriggerOutcome, DeckError> {
    let context = Context::new();
    let decision =
        engine.decide(&id.to_string(), &context).map_err(|err| DeckError(format!("{err:?}")))?;
    Ok(match decision {
        Decision::Run(actions) => {
            hikari_automation::spawn_isolated(actions, deck_sink);
            DeckTriggerOutcome::Dispatched
        }
        Decision::Refused(reason) => DeckTriggerOutcome::Refused { reason: format!("{reason:?}") },
    })
}

/// Recovers the engine lock even if a prior panic poisoned it — a poisoned mutex must
/// never turn a deck press into a crashed app (the same "Let It Crash, don't propagate"
/// spirit as `hikari_automation::execution`); the recovered state is still valid data,
/// just possibly mid-write when the panic happened.
fn lock_engine<'a>(state: &'a State<'a, DeckState>) -> std::sync::MutexGuard<'a, AutomationEngine> {
    state.0.lock().unwrap_or_else(|poisoned| poisoned.into_inner())
}

#[tauri::command]
pub(crate) fn deck_list_keys(state: State<DeckState>) -> Vec<DeckKey> {
    list_deck_keys(&lock_engine(&state))
}

// Async command (unlike `deck_list_keys`): `spawn_isolated` needs a live Tokio reactor
// (`hikari_automation::execution`), which Tauri only guarantees inside its async command
// dispatch path — a sync command has no such guarantee (proven by the pre-fix test
// failure: "there is no reactor running").
#[tauri::command]
pub(crate) async fn deck_trigger_key(
    state: State<'_, DeckState>,
    id: String,
) -> Result<DeckTriggerOutcome, DeckError> {
    trigger_key(&lock_engine(&state), &id)
}

#[cfg(test)]
mod tests {
    use std::time::{Duration, Instant};

    use hikari_automation::{ChatCommandWhitelist, RefusalReason, Trigger};

    use super::*;

    fn button_automation(id: &str) -> Automation {
        Automation {
            id: id.to_string(),
            name: format!("Automation {id}"),
            trigger: Trigger::Button,
            conditions: vec![],
            actions: vec![Action::Wait { millis: 0 }],
            active: true,
        }
    }

    fn event_automation(id: &str) -> Automation {
        Automation {
            id: id.to_string(),
            name: format!("Event {id}"),
            trigger: Trigger::Event { event_name: "follow".to_string() },
            conditions: vec![],
            actions: vec![],
            active: true,
        }
    }

    #[test]
    fn should_show_button_automation_as_key() {
        // ADR-012's rule already lives in the engine (`should_never_expose_event_trigger_as_deck_key`,
        // hikari-automation/src/model.rs) — this test proves the DECK CONSUMES that rule
        // through `deck_eligible_automations()` rather than re-deriving it itself.
        let mut engine = AutomationEngine::new(ChatCommandWhitelist::default());
        engine.register(button_automation("marker")).expect("valid button automation registers");
        engine.register(event_automation("on-follow")).expect("valid event automation registers");

        let keys = list_deck_keys(&engine);

        assert_eq!(keys, vec![DeckKey { id: "marker".to_string(), label: "Automation marker".to_string() }]);
    }

    #[test]
    fn should_show_no_keys_when_engine_empty() {
        // First-launch state (no Automations screen built yet, B-auto Notes) must be an
        // honest empty list, never a placeholder pretending something is assigned.
        let engine = AutomationEngine::new(ChatCommandWhitelist::default());
        assert_eq!(list_deck_keys(&engine), Vec::<DeckKey>::new());
    }

    #[tokio::test]
    async fn should_dispatch_when_active_button_pressed() {
        let mut engine = AutomationEngine::new(ChatCommandWhitelist::default());
        engine.register(button_automation("marker")).expect("valid button automation registers");

        let outcome = trigger_key(&engine, "marker").expect("known id decides");

        assert_eq!(outcome, DeckTriggerOutcome::Dispatched);
    }

    #[test]
    fn should_refuse_when_inactive_button_pressed() {
        let mut engine = AutomationEngine::new(ChatCommandWhitelist::default());
        let mut inactive = button_automation("marker");
        inactive.active = false;
        engine.register(inactive).expect("valid automation registers even inactive");

        let outcome = trigger_key(&engine, "marker").expect("known id decides");

        assert_eq!(outcome, DeckTriggerOutcome::Refused { reason: format!("{:?}", RefusalReason::Inactive) });
    }

    #[test]
    fn should_error_when_unknown_key_pressed() {
        let engine = AutomationEngine::new(ChatCommandWhitelist::default());
        assert!(trigger_key(&engine, "ghost").is_err());
    }

    #[tokio::test]
    async fn should_trigger_action_under_100ms_when_pressed() {
        // Real wall-clock measurement (Quality.md "proof, never assertion") of decide +
        // dispatch — never the action's own duration, see `trigger_key` doc.
        let mut engine = AutomationEngine::new(ChatCommandWhitelist::default());
        engine.register(button_automation("marker")).expect("valid button automation registers");

        let started = Instant::now();
        let outcome = trigger_key(&engine, "marker").expect("known id decides");
        let elapsed = started.elapsed();

        assert_eq!(outcome, DeckTriggerOutcome::Dispatched);
        assert!(elapsed < Duration::from_millis(100), "trigger_key took {elapsed:?}, budget is 100ms");
    }

    #[tokio::test]
    async fn should_work_when_offline() {
        // `trigger_key`/`list_deck_keys` compile against zero network crate (no reqwest,
        // no tokio networking feature is even enabled in hikari-automation's Cargo.toml)
        // — offline-safety here is a structural property, not a runtime toggle. This test
        // proves the observable half: the full decide -> dispatch path for a LOCAL action
        // set succeeds with no server, no mock, no network stack running anywhere in the
        // test process — exactly the conditions of a machine with the network off.
        let mut engine = AutomationEngine::new(ChatCommandWhitelist::default());
        let mut automation = button_automation("marker");
        automation.actions = vec![
            Action::SendChatMessage { message: "brb".to_string() },
            Action::Wait { millis: 0 },
        ];
        engine.register(automation).expect("valid button automation registers");

        let outcome = trigger_key(&engine, "marker").expect("known id decides without any network I/O");

        assert_eq!(outcome, DeckTriggerOutcome::Dispatched);
    }

    #[test]
    fn should_recover_engine_lock_when_poisoned() {
        // A poisoned mutex (some unrelated panic while holding the lock) must never turn
        // a deck press into a second crash — proves `lock_engine`'s recovery path.
        use std::panic;
        use std::sync::Arc;

        let state = Arc::new(DeckState::default());
        {
            let poison_state = Arc::clone(&state);
            let _ = panic::catch_unwind(panic::AssertUnwindSafe(|| {
                let _guard = poison_state.0.lock().unwrap();
                panic!("simulated poisoning");
            }));
        }

        // Recovering directly on the inner Mutex proves the SAME strategy `lock_engine`
        // uses; `lock_engine` itself needs a live Tauri `State<T>`, out of reach headless.
        let recovered = state.0.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        assert_eq!(list_deck_keys(&recovered), Vec::<DeckKey>::new());
    }
}
