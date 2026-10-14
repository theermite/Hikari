//! Un seul renouvellement de jeton à la fois.
//!
//! Au démarrage, plusieurs parties de l'application demandent « le jeton utilisable » en
//! même temps : le moteur (destination de diffusion), le chat, les infos du direct. Quand
//! le jeton d'accès a expiré, chacune lançait SON renouvellement avec le MÊME jeton de
//! renouvellement. Twitch en émet un nouveau à chaque fois : les appels simultanés se
//! concurrencent, et le perdant reçoit un refus — ce qui laissait le moteur sans
//! destination de diffusion (2026-10-14).
//!
//! Ici, tous les appelants passent par une même porte : le premier renouvelle, les autres
//! attendent, relisent le coffre et trouvent le jeton déjà neuf.

use std::future::Future;

/// Rend le jeton utilisable, en ne renouvelant qu'UNE fois même si `n` appelants arrivent
/// ensemble.
///
/// - `load` relit le jeton rangé (le coffre) ; `None` = aucun compte.
/// - `is_usable` dit si un jeton se suffit tel quel.
/// - `renew` renouvelle ET range le résultat avant de rendre la main : c'est ce rangement
///   que les appelants en attente retrouvent en relisant.
pub async fn renew_once<T, L, U, R, Fut>(
    gate: &tokio::sync::Mutex<()>,
    load: L,
    is_usable: U,
    renew: R,
) -> Result<Option<T>, String>
where
    L: Fn() -> Option<T>,
    U: Fn(&T) -> bool,
    R: FnOnce(T) -> Fut,
    Fut: Future<Output = Result<T, String>>,
{
    let Some(token) = load() else {
        return Ok(None);
    };
    if is_usable(&token) {
        return Ok(Some(token));
    }
    let _turn = gate.lock().await;
    // Pendant l'attente, un autre appelant a pu renouveler et ranger le jeton neuf.
    let Some(current) = load() else {
        return Ok(None);
    };
    if is_usable(&current) {
        return Ok(Some(current));
    }
    renew(current).await.map(Some)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};
    use std::sync::{Arc, Mutex};

    /// Un « coffre » de test : le jeton rangé, et combien de fois on a renouvelé.
    #[derive(Clone)]
    struct Vault {
        stored: Arc<Mutex<Option<u32>>>,
        renewals: Arc<AtomicU32>,
    }

    impl Vault {
        fn with(token: Option<u32>) -> Self {
            Self {
                stored: Arc::new(Mutex::new(token)),
                renewals: Arc::new(AtomicU32::new(0)),
            }
        }
        fn load(&self) -> Option<u32> {
            *self.stored.lock().unwrap()
        }
    }

    /// Le jeton 0 est périmé, tout autre est utilisable.
    fn usable(token: &u32) -> bool {
        *token != 0
    }

    async fn call(gate: &tokio::sync::Mutex<()>, vault: &Vault) -> Result<Option<u32>, String> {
        let v = vault.clone();
        let renew_vault = vault.clone();
        renew_once(
            gate,
            move || v.load(),
            usable,
            move |_old| async move {
                // Plusieurs tours de planification : les autres appelants arrivent pendant
                // que celui-ci « parle à Twitch ».
                for _ in 0..5 {
                    tokio::task::yield_now().await;
                }
                renew_vault.renewals.fetch_add(1, Ordering::SeqCst);
                *renew_vault.stored.lock().unwrap() = Some(7);
                Ok(7)
            },
        )
        .await
    }

    #[tokio::test]
    async fn should_renew_only_once_when_many_callers_arrive_together() {
        let gate = tokio::sync::Mutex::new(());
        let vault = Vault::with(Some(0));

        let results = tokio::join!(
            call(&gate, &vault),
            call(&gate, &vault),
            call(&gate, &vault),
            call(&gate, &vault),
            call(&gate, &vault),
        );

        assert_eq!(vault.renewals.load(Ordering::SeqCst), 1);
        let (a, b, c, d, e) = results;
        assert!([a, b, c, d, e].iter().all(|r| *r == Ok(Some(7))));
    }

    #[tokio::test]
    async fn should_not_renew_a_token_that_is_still_usable() {
        let gate = tokio::sync::Mutex::new(());
        let vault = Vault::with(Some(3));

        let result = call(&gate, &vault).await;

        assert_eq!(result, Ok(Some(3)));
        assert_eq!(vault.renewals.load(Ordering::SeqCst), 0);
    }

    #[tokio::test]
    async fn should_report_no_account_without_renewing_anything() {
        let gate = tokio::sync::Mutex::new(());
        let vault = Vault::with(None);

        let result = call(&gate, &vault).await;

        assert_eq!(result, Ok(None));
        assert_eq!(vault.renewals.load(Ordering::SeqCst), 0);
    }

    #[tokio::test]
    async fn should_pass_a_refused_renewal_back_to_the_caller() {
        let gate = tokio::sync::Mutex::new(());
        let vault = Vault::with(Some(0));
        let v = vault.clone();

        let result = renew_once(
            &gate,
            move || v.load(),
            usable,
            |_old| async { Err::<u32, String>("renouvellement refusé".to_string()) },
        )
        .await;

        assert_eq!(result, Err("renouvellement refusé".to_string()));
    }
}
