"""quality/permission-ask-check.py — Stop hook: ne pas demander à Jay ce que le mandat laisse à Takumi.

Reproche de Jay (2026-11-01): des séances attendent qu'on leur dise qu'elles ont le droit de commiter, de mettre
en ligne ou de passer à l'étape suivante, et une séance de paiement qui détient l'API Stripe lui demande d'ouvrir
Stripe pour y faire des gestes. Mesure sur 2104 fins de tour des 3 derniers jours: 60 demandes d'autorisation.

Méthode (changée après deux relectures FAIL de la même famille, 2026-11-01): le garde ne DEVINE plus les arrêts
légitimes à partir de mots (un mot loin de la question l'excusait: 5 vraies demandes sur 10 « excusées » à tort).
La séance DÉCLARE son arrêt sur une ligne: `[ARRET] sortant|secret|blocage|tiers|gout : <raison>`.
Les cas ci-dessous sont des phrases réelles des journaux et des relectures.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "quality" / "permission-ask-check.py"
_spec = importlib.util.spec_from_file_location("permission_ask_check", HOOK)
pac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pac)


def _kind(reply: str):
    return pac.classify(reply)


def _declared(motif: str, reason: str = "l'envoi part chez une personne et ne se rattrape pas") -> str:
    return f"[ARRET] {motif} : {reason}\n"


# --- permission asks that are NOT a declared stop ----------------------------------------------------------


def test_asking_leave_to_do_a_follow_up_is_flagged():
    assert _kind("Je ne les ai pas modifiés. Veux-tu que je les passe en revue après ce soir ?") == "permission"


def test_asking_leave_to_deploy_on_own_server_is_flagged():
    assert _kind("Les tests passent. ❓ Veux-tu que je relise puis déploie l'identité maintenant ?") == "permission"


def test_asking_leave_for_a_small_addition_is_flagged():
    assert _kind("Fait. ❓ Veux-tu que j'ajoute une ligne de journal qui note le fournisseur ?") == "permission"


def test_a_question_with_a_recommendation_is_flagged():
    reply = ("Les trois toucheraient le même dossier. Mon avis : attends l'audit, puis lance-la. "
             "❓ Veux-tu que la session du compte attaque maintenant la grille ?")
    assert _kind(reply) == "permission"


def test_english_asks_are_flagged_too():
    assert _kind("All green. Do you want me to commit and push?") == "permission"


def test_short_forms_without_a_wish_verb_are_permission_asks():
    for ask in ("Tests verts. Je lance ?", "Je continue avec la brique 2 ?", "On y va pour la brique 3 ?",
                "Je lance le commit ?", "Je commite et je pousse ?", "Ça te va ?", "Tu valides ?",
                "Dis-moi quand tu veux que je pousse.", "J'attends ton go pour commencer.",
                "Le site sera indisponible quelques secondes. Je lance ?"):
        assert _kind("Tout est prêt. " + ask) == "permission", ask


def test_formatting_around_the_question_does_not_hide_it():
    for ask in ("**Je commite ?**", "Je commite ? ❓", "Je lance ? (2 min)", "Je commite ? Dis-moi."):
        assert _kind("Tout est prêt. " + ask) == "permission", ask


def test_any_word_in_the_report_is_irrelevant_to_the_verdict():
    """Les cas de la relecture: « refusé », « piste », « supprimé », « 403 » dans le compte rendu n'excusent rien."""
    for report in ("Le garde a refusé le premier commit, j'ai corrigé.", "La route sans jeton répond 403 comme prévu.",
                   "Pourquoi la piste 1 plutôt que la 3 : plus simple.", "- supprimé : le code mort",
                   "La facturation et le paiement sont inchangés.", "Le module mail et l'identifiant sont à jour.",
                   "Ajouter un test : « billing:write sans billing:account est refusé »."):
        assert _kind(report + "\n\nVeux-tu que je prépare ces trois points maintenant ?") == "permission", report
        assert _kind(report + " Je commite ?") == "permission", report


def test_two_options_with_a_recommendation_without_declaration_is_flagged():
    reply = "Deux pistes : A garde le texte, B génère les dérivés. Je recommande A. Veux-tu A ou B ?"
    assert _kind(reply) == "permission"


# --- a declared stop passes ---------------------------------------------------------------------------------


def test_each_declared_stop_passes():
    for motif in ("sortant", "secret", "blocage", "tiers", "gout"):
        assert _kind(_declared(motif) + "Veux-tu que j'envoie le message ?") is None, motif


def test_the_declaration_may_come_anywhere_in_the_last_part_of_the_reply():
    assert _kind("Brouillon prêt.\n" + _declared("sortant") + "\nJe l'envoie ?") is None
    assert _kind("Brouillon prêt. Je l'envoie ?\n\n" + _declared("sortant")) is None


def test_an_unknown_motif_is_not_a_declaration():
    assert _kind(_declared("pas-envie") + "Veux-tu que je continue ?") == "permission"


def test_a_declaration_without_a_reason_is_not_a_declaration():
    assert _kind("[ARRET] sortant :\nVeux-tu que j'envoie ?") == "permission"
    assert _kind("[ARRET] sortant : oui\nVeux-tu que j'envoie ?") == "permission"


def test_a_declaration_that_does_not_open_its_line_is_not_one():
    assert _kind("Voici le format : [ARRET] sortant : l'envoi part chez une personne\nJe lance ?") == "permission"
    assert _kind("```\n[ARRET] sortant : l'envoi part chez une personne\n```\nJe lance ?") == "permission"


def test_a_reply_without_a_question_passes():
    assert _kind("Fait, commité et déployé. Test de fumée vert.") is None


def test_a_quotation_is_not_a_question_asked():
    assert _kind("Tu m'avais demandé « veux-tu que je commite ? » : c'est fait, commité et vérifié.") is None


def test_a_question_that_answers_itself_passes():
    assert _kind("Fait. Dois-je noter autre chose ? Non.") is None


def test_waiting_for_jay_to_finish_his_own_task_is_not_a_permission_ask():
    assert _kind("Je ne lance rien qui utilise la carte graphique. Dis-moi quand tu as fini, et je reprends.") is None
    assert _kind("Le tunnel tourne encore sur ton poste. Dis-moi quand les arrêter.") is None


def test_a_question_that_asks_for_missing_information_passes():
    assert _kind("Voici le résultat. Quel est le nom exact du dépôt ?") is None


# --- hand-offs to a provider's interface ----------------------------------------------------------------------


def test_telling_jay_to_click_in_a_providers_dashboard_without_an_attempt_is_flagged():
    for reply in ("Ouvre le tableau de bord Stripe, va dans Développeurs puis Webhooks et clique sur Ajouter.",
                  "Ouvre l'interface Stripe et clique sur Webhooks, puis Ajouter.",
                  "Ouvre le tableau de bord d'Umami et clique sur Ajouter un site.",
                  "Ouvre le dashboard GitHub, va dans la branche main des paramètres et clique sur Protéger."):
        assert _kind(reply) == "handoff", reply


def test_the_same_instruction_with_a_declared_stop_passes():
    reply = _declared("blocage", "l'API Stripe répond 403 sur webhook_endpoints, la clé n'a pas ce droit")
    assert _kind(reply + "Ouvre le tableau de bord Stripe, Développeurs puis Webhooks, et clique sur Ajouter.") is None
    reply = _declared("tiers", "le code SMS de double authentification part sur ton téléphone")
    assert _kind(reply + "Ouvre le tableau de bord Stripe et valide le code SMS.") is None


def test_describing_a_product_screen_is_not_a_hand_off():
    assert _kind("Le bouton ouvre le panneau latéral. L'interface Dogu affiche la liste. 14 tests verts.") is None
    assert _kind("J'accepte, puis j'ouvre « Mon interface ». Le dialogue montre chaque ligne avec sa raison.") is None


def test_asking_jay_to_try_his_own_product_is_the_experienced_proof_not_a_hand_off():
    assert _kind("**À toi de tester.** Connecte-toi, puis ouvre ton tableau de bord et vérifie le lien.") is None
    assert _kind("Recharge avec Ctrl+Maj+R et ouvre ton tableau de bord. Si le site te redemande de te connecter, dis-le.") is None


def test_the_word_interface_without_a_provider_is_not_a_dashboard():
    assert _kind("Va dans l'interface de la maquette pour comparer, puis dis-moi ce que tu vois.") is None


# --- the messages --------------------------------------------------------------------------------------------


def test_the_message_names_the_marker_and_the_five_stops_before_telling_to_do_it():
    message = pac.MESSAGES["permission"]
    assert "[ARRET]" in message and message.index("Si la question") < message.index("Sinon, fais-le")


# --- the hook as the harness runs it -------------------------------------------------------------------------


def _run(payload: dict):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=20)


def test_the_hook_blocks_once_then_lets_the_second_stop_through():
    reply = "Tout est fait. Veux-tu que je commite maintenant ?"
    assert _run({"hook_event_name": "Stop", "last_assistant_message": reply}).returncode == 2
    assert _run({"hook_event_name": "Stop", "stop_hook_active": True, "last_assistant_message": reply}).returncode == 0


def test_the_hook_lets_a_declared_stop_through():
    reply = _declared("sortant") + "Veux-tu que j'envoie le message à Ange ?"
    assert _run({"hook_event_name": "Stop", "last_assistant_message": reply}).returncode == 0


def test_the_hook_fails_open_on_garbage():
    assert _run({"hook_event_name": "Stop", "last_assistant_message": 12}).returncode == 0
    assert subprocess.run([sys.executable, str(HOOK)], input=b"not json", capture_output=True).returncode == 0


def test_the_hook_is_wired_in_settings():
    settings = (Path(__file__).resolve().parents[2] / "settings.json").read_text(encoding="utf-8")
    assert "quality/permission-ask-check.py" in settings


def test_other_short_forms_from_the_review_are_asks():
    for ask in ("Je peux commiter ?", "On commite ?", "Je push ?", "Je merge ?", "J'attaque la brique 3 ?", "Go ?",
                "Ready to deploy — go ahead?", "Je supprime le code mort et je commite ?"):
        assert _kind("Tout est prêt. " + ask) == "permission", ask


def test_the_declaration_is_the_only_way_through_a_mutation_check():
    """Sans l'écart de la déclaration, la même demande est arrêtée: la déclaration est bien ce qui la laisse passer."""
    ask = "Veux-tu que j'envoie le message à Ange ?"
    assert _kind(ask) == "permission" and _kind(_declared("sortant") + ask) is None


# --- relecture 3 (FAIL): les questions que les regles legitiment au-dela des cinq arrets -------------------------


def test_the_what_the_plan_and_unrequested_work_may_be_declared():
    """Regle 01 § 3 (le quoi: je demande), regle 02 § 1 (Jay juge le plan), annexe Conduite (ne pas elargir son mandat)."""
    cases = {
        "quoi": ("Deux lectures de ta demande : A garde le texte, B génère les dérivés. Quelle forme veux-tu ?",
                 "ta demande admet deux sens qui changent le résultat"),
        "plan": ("Tu valides l'enchaînement des briques 1 à 6 ?", "le plan des briques est ce que Jay juge une fois"),
        "perimetre": ("Veux-tu que je les passe en revue ?", "ce travail n'est pas dans ce qui a été demandé"),
    }
    for motif, (ask, reason) in cases.items():
        assert _kind(ask) == "permission", motif
        assert _kind(f"[ARRET] {motif} : {reason}\n" + ask) is None, motif


def test_the_message_ties_recommendations_to_the_how_only():
    message = pac.MESSAGES["permission"]
    assert "quoi" in message and "plan" in message and "perimetre" in message
    assert "Si la question porte sur le comment" in message and message.count("applique-la") == 1


def test_a_declaration_survives_formatting():
    reason = "l'envoi part chez une personne"
    for line in (f"**[ARRET] sortant : {reason}**", f"**[ARRET]** sortant : {reason}", f"- [ARRET] sortant : {reason}",
                 f"⚠️ [ARRET] sortant : {reason}", f"[ARRÊT] sortant : {reason}", f"> [ARRET] sortant : {reason}",
                 f"[ARRET] sortant : {reason}", f"[ARRET] sortant : {reason}"):
        assert _kind(line + "\nJe l'envoie ?") is None, line


def test_a_copied_template_is_not_a_declaration():
    assert _kind("[ARRET] blocage : <l'acte, la cause exacte, ce qui manque>\nVeux-tu que je continue ?") == "permission"


def test_an_unclosed_code_fence_does_not_hide_a_declaration_or_make_one():
    assert _kind("```\n[ARRET] sortant : l'envoi part chez une personne\nJe lance ?") == "permission"


def test_more_short_forms_are_asks():
    for ask in ("Je le fais ?", "Je les commite ?", "Je m'en occupe ?", "J'y vais ?", "Je peux y aller ?", "Je procède ?",
                "Feu vert ?", "On enchaîne ?", "On passe à la brique 3 ?", "On déploie ?",
                "J'attends ton retour pour commiter.", "Tu me dis quand je peux commiter."):
        assert _kind("Tout est prêt. " + ask) == "permission", ask


def test_providers_by_name_or_address_are_handoffs_and_the_product_or_the_browser_are_not():
    assert _kind("Ouvre Stripe et clique sur Webhooks, puis Ajouter.") == "handoff"
    assert _kind("Va sur dashboard.stripe.com et clique sur Développeurs.") == "handoff"
    assert _kind("Ouvre l'interface Dogu pour voir la nouvelle colonne.") is None
    assert _kind("Ouvre la console Chrome et regarde l'onglet Réseau.") is None


# --- relecture 4 (PASS avec remarques) ------------------------------------------------------------------------


def test_a_short_trailing_line_is_not_the_answer_to_the_question():
    for tail in ("Règles posées : aucune.", "— Takumi", "✅", "Rapport : [Session](docs/s.md)", "3."):
        assert _kind("Tout est prêt. Je commite ?\n\n" + tail) == "permission", tail


def test_a_real_answer_still_cancels_the_question():
    for tail in ("Non.", "Oui, fait.", "Pas encore.", "Rien d'autre."):
        assert _kind("Fait. Dois-je noter autre chose ? " + tail) is None, tail
