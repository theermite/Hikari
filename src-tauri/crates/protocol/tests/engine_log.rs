//! Tests écrits AVANT le code (TDG).
//!
//! Lignes copiées TELLES QUELLES du journal de la machine de Jay, le 2026-09-06 — jamais
//! inventées. Une ligne inventée prouverait le filtre contre lui-même, pas contre le
//! terrain (leçon du 2026-08-04 : « l'échantillon ment »).

use hikari_protocol::user_visible_engine_log;

#[test]
fn should_show_the_reason_a_camera_stays_black() {
    // LA ligne qui manquait : la troisième caméra de Jay n'apparaissait pas, et le moteur
    // en donnait la cause exacte depuis le début.
    let line = "[Warning] DShow: Run failed (0x800718CF): A camera interface doesn't have \
                the desired bandwidth for data transfer.";

    let shown = user_visible_engine_log(line).expect("un échec doit être montré");

    assert!(shown.contains("bandwidth"), "shown = {shown}");
    assert!(
        !shown.starts_with("[Warning]"),
        "le marqueur est retiré : {shown}"
    );
}

#[test]
fn should_show_what_the_engine_calls_an_error() {
    let line = "[Error] impossible de creer la sortie video";

    assert!(user_visible_engine_log(line).is_some());
}

#[test]
fn should_stay_silent_when_the_engine_had_nothing_to_say() {
    // Ligne remontée dans le bandeau de Jay le 2026-09-06, à tort. « (null) » est
    // littéralement le message manquant : le greffon a signalé une erreur sans dire
    // laquelle. La montrer alarme sans rien apprendre, et elle revient à chaque caméra
    // ouverte.
    let line = "[Error] [NVIDIA Video Effect: '(null)']";

    assert_eq!(user_visible_engine_log(line), None);
}

#[test]
fn should_stay_silent_on_a_comfort_warning() {
    // Cet avertissement arrive en rafale et ne concerne pas l'utilisateur. Le montrer
    // ferait un bandeau que personne ne lit — donc un bandeau muet quand ça compte.
    let line = "[Debug] Audio timestamp for 'USB camera' exceeded TS_SMOOTHING_THRESHOLD";

    assert_eq!(user_visible_engine_log(line), None);
}

#[test]
fn should_stay_silent_on_a_warning_that_announces_no_failure() {
    let line = "[Warning] DShow: Device may be in use";

    assert_eq!(user_visible_engine_log(line), None);
}

#[test]
fn should_stay_silent_while_probing_the_devices() {
    // La sonde interroge chaque appareil : elle échoue par construction sur ceux qui ne
    // répondent pas. Remonter ça ferait paniquer sur le fonctionnement normal.
    for line in [
        "[Warning] hikari-camera-probe: DecodeDeviceId failed",
        "[Warning] hikari-camera-probe: Video configuration failed",
    ] {
        assert_eq!(user_visible_engine_log(line), None, "line = {line}");
    }
}

#[test]
fn should_stay_silent_when_an_inventory_asks_who_is_there() {
    // Ligne remontée dans le bandeau de Jay le 2026-09-06, à tort. Faire l'inventaire des
    // appareils, c'est demander « qui répond ? » — une absence de réponse EST la réponse,
    // pas une panne. Même nature que la sonde caméra, déjà écartée.
    let line = "[Warning] [WASAPISource::TryInitialize]:[{0.0.0.00000000}.                {17baa00b-a184-4f35-87b0-29ccf3e02dfe}] Failed to enumerate device: 80070490";

    assert_eq!(user_visible_engine_log(line), None);
}

#[test]
fn should_still_show_a_failure_that_is_not_an_inventory() {
    // Le garde-fou du test précédent ne doit pas emporter le cas qui compte.
    let line = "[Warning] DShow: Run failed (0x800718CF): A camera interface doesn't have                 the desired bandwidth for data transfer.";

    assert!(user_visible_engine_log(line).is_some());
}

#[test]
fn should_stay_silent_on_the_ordinary_chatter() {
    for line in [
        "[Info] \tresolution: 1920x1080",
        "[Debug] DShow: Video media type changed",
        "\tformat: MJPEG",
        "",
    ] {
        assert_eq!(user_visible_engine_log(line), None, "line = {line}");
    }
}

#[test]
fn should_ignore_the_indentation_the_engine_writes() {
    let line = "   [Error] quelque chose a cassé";

    assert_eq!(
        user_visible_engine_log(line).as_deref(),
        Some("quelque chose a cassé")
    );
}
