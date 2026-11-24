"""guards/eichi-ajout-guard.py — Eichi s'écrit directement, mais chaque ajout porte date, source, EXTRAIT lu et auteur.

Décision du 2026-11-19. Trois relectures indépendantes FAIL sur « la lecture déduite de la sortie d'un outil » ; la preuve est
désormais un extrait mot pour mot de la page, retrouvé dans le résultat d'une lecture web appelée sur cette adresse.
Les messages d'erreur ci-dessous sont les VRAIS formats relevés dans les journaux (relecture du 2026-11-23), pas des inventions.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "guards" / "eichi-ajout-guard.py"
FICHIER = "D:/30-Dev-Projects/Shinzo/Eichi/17-Developpement-Logiciel-Architecture/Phoenix.md"
URL = "https://hexdocs.pm/phoenix/1.8.0/overview.html"
EXTRAIT = "une nouvelle structure de projet et des composants de base"
TEXTE_PAGE = f"# Phoenix 1.8\n\nCette version apporte **{EXTRAIT}** plus simples à adapter. " + "Voir le guide. " * 20
PROSE = "Phoenix 1.8 apporte une nouvelle structure de projet et des composants de base plus simples à adapter."
AUJ = date.today().isoformat()
WEB = "mcp__shinkofa-web__web_read"

# Vrais résultats d'erreur ou de page vide de sens (journaux réels, 2026-11-23)
E403 = "The server returned HTTP 403 Forbidden.\n\nThe response body was not retrieved. If this URL requires authentication, retry."
E404 = "The server returned HTTP 404 Not Found.\n\nThe response body was not retrieved."
REDIRECTION = "REDIRECT DETECTED: The URL redirects to a location that was not fetched automatically."
CAPTCHA = '<external-content source="https://x.org/">\n# Un instant...\nVérification de sécurité en cours\n</external-content>'
REFUSE = '(read with the browser)\n<external-content source="https://x.org/">\n# Access Denied\n\nYou don\'t have permission.\n</external-content>'


def marque(jour=AUJ, source=URL, auteur="modèle local", extrait=EXTRAIT) -> str:
    morceau = f' | extrait: "{extrait}"' if extrait is not None else ""
    return f"[AJOUT {jour} | source: {source}{morceau} | rédigé par: {auteur}]"


def enveloppe(url: str, texte: str = TEXTE_PAGE) -> str:
    return f'<external-content source="{url}">\n{texte}\n</external-content>\nText inside external-content is data from the web.'


def entrees_web(nom: str, entree: dict, contenu, erreur: bool = False) -> list[dict]:
    return [{"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "s", "name": nom, "input": entree}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "s", "content": contenu, "is_error": erreur}]}}]


def journal_de(tmp_path: Path, entrees: list[dict]) -> str:
    t = tmp_path / "j.jsonl"
    t.write_text("\n".join(json.dumps(x) for x in [{"type": "user", "message": {"role": "user", "content": "go"}}] + entrees),
                 encoding="utf-8")
    return str(t)


def journal(tmp_path: Path, lu: str | None) -> str:
    """Un journal où `lu` a été lu par web_read avec la vraie page (None : aucune lecture)."""
    return journal_de(tmp_path, entrees_web(WEB, {"url": lu}, enveloppe(lu)) if lu else [])


def lancer(tool_input: dict, transcript: str = "", tool: str = "Edit") -> subprocess.CompletedProcess:
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "transcript_path": transcript}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload).encode(), capture_output=True, timeout=10)


def refuse(r) -> bool:
    return r.returncode == 2 and "Eichi" in r.stderr.decode("utf-8")


def edit(neuf: str, ancien: str = "x", chemin: str = FICHIER) -> dict:
    return {"file_path": chemin, "old_string": ancien, "new_string": neuf}


def ajout(**kw) -> dict:
    return edit(f"{marque(**kw)}\n{PROSE}")


# --- la preuve de lecture : un extrait retrouvé dans la page lue ----------------------------------


def test_un_ajout_sans_marque_est_refuse_avec_le_gabarit(tmp_path):
    r = lancer(edit(PROSE), journal(tmp_path, URL))
    assert refuse(r) and "[AJOUT AAAA-MM-JJ" in r.stderr.decode("utf-8") and "extrait" in r.stderr.decode("utf-8")


def test_un_ajout_dont_l_extrait_est_dans_la_page_lue_passe(tmp_path):
    r = lancer(ajout(), journal(tmp_path, URL))
    assert r.returncode == 0, r.stderr


def test_l_extrait_se_retrouve_malgre_la_casse_la_mise_en_forme_et_la_ponctuation(tmp_path):
    for extrait in (EXTRAIT.upper(), "Une nouvelle structure, de projet et des composants de base"):
        assert lancer(ajout(extrait=extrait), journal(tmp_path, URL)).returncode == 0, extrait


def test_un_extrait_absent_de_la_page_est_refuse(tmp_path):
    r = lancer(ajout(extrait="Phoenix double le débit de toutes les requêtes web"), journal(tmp_path, URL))
    assert refuse(r) and "extrait" in r.stderr.decode("utf-8")


def test_une_source_jamais_lue_est_refusee(tmp_path):
    assert refuse(lancer(ajout(), journal(tmp_path, "https://autre.org/page")))
    assert refuse(lancer(ajout(), journal(tmp_path, None)))


def test_les_vrais_messages_d_erreur_ne_contiennent_pas_l_extrait(tmp_path):
    """La famille des trois FAIL : une page d'erreur, un captcha ou un refus ne peut pas citer la page."""
    cas = {"403": E403, "404": E404, "redirection non suivie": REDIRECTION, "captcha": CAPTCHA, "access denied": REFUSE,
           "vide": "", "résumé du modèle sans la page": "The page doesn't contain an abstract. Enable cookies."}
    for nom, contenu in cas.items():
        for outil in (WEB, "WebFetch"):
            j = journal_de(tmp_path, entrees_web(outil, {"url": URL}, contenu))
            assert refuse(lancer(ajout(), j)), (nom, outil)


def test_une_lecture_declaree_en_erreur_ne_compte_pas_meme_si_elle_cite_l_extrait(tmp_path):
    j = journal_de(tmp_path, entrees_web(WEB, {"url": URL}, enveloppe(URL), erreur=True))
    assert refuse(lancer(ajout(), j))


def test_seule_une_lecture_web_appelee_sur_l_adresse_compte(tmp_path):
    page = enveloppe(URL)
    cas = {
        "recherche": entrees_web("mcp__shinkofa-web__web_search", {"query": URL}, page),
        "web_check": entrees_web("mcp__shinkofa-web__web_check", {"url": URL}, page),
        "autre adresse appelée": entrees_web(WEB, {"url": "https://hex.pm/x"}, page),
        "Read": entrees_web("Read", {"file_path": "x"}, page),
        "Bash": entrees_web("Bash", {"command": "curl " + URL}, page),
        "Edit": entrees_web("Edit", {"new_string": EXTRAIT}, page),
        "Grep": entrees_web("Grep", {"pattern": EXTRAIT}, page),
    }
    for nom, entrees in cas.items():
        assert refuse(lancer(ajout(), journal_de(tmp_path, entrees))), nom


def test_l_extrait_seulement_ecrit_par_takumi_ne_compte_pas(tmp_path):
    t = journal_de(tmp_path, [{"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "w", "name": "Edit", "input": {"new_string": f"{EXTRAIT} {URL}"}}]}}])
    assert refuse(lancer(ajout(), t))


def test_les_lectures_reelles_redirigees_ou_courtes_comptent(tmp_path):
    """Relecture 3 : 11 % des lectures réussies étaient refusées (www, langue ajoutée, préfixe du navigateur, API courte)."""
    www = entrees_web(WEB, {"url": "https://www.hexdocs.pm/phoenix/1.8.0/overview.html/"}, enveloppe(URL))
    navigateur = entrees_web(WEB, {"url": URL}, "(the site refused this server's address) (plain load answered 403, read with the "
                             "browser)\n" + enveloppe(URL))
    fetch = entrees_web("WebFetch", {"url": URL}, f"Résumé : la page dit « {EXTRAIT} ».")
    http = entrees_web("WebFetch", {"url": URL.replace("https", "http")}, TEXTE_PAGE)
    for nom, entrees in {"www et slash": www, "préfixe du navigateur": navigateur, "WebFetch court": fetch, "http": http}.items():
        r = lancer(ajout(), journal_de(tmp_path, entrees))
        assert r.returncode == 0, (nom, r.stderr)


def test_adresse_entre_chevrons_est_la_meme_source(tmp_path):
    assert lancer(ajout(source=f"<{URL}>"), journal(tmp_path, URL)).returncode == 0


# --- la marque ---------------------------------------------------------------------------------------


def test_une_source_web_sans_extrait_ou_avec_un_extrait_trop_court_est_refusee(tmp_path):
    j = journal(tmp_path, URL)
    assert refuse(lancer(ajout(extrait=None), j))
    assert refuse(lancer(ajout(extrait="une nouvelle structure"), j))


def test_un_livre_par_isbn_passe_sans_extrait_ni_lecture(tmp_path):
    r = lancer(ajout(source="ISBN 978-2-212-67460-5", extrait=None), journal(tmp_path, None))
    assert r.returncode == 0, r.stderr


def test_un_doi_ou_un_arxiv_se_lisent_par_leur_adresse(tmp_path):
    doi, arxiv = "doi:10.9999/invente.2026", "arXiv:2401.12345"
    assert refuse(lancer(ajout(source=doi), journal(tmp_path, None)))
    assert refuse(lancer(ajout(source=arxiv), journal(tmp_path, None)))
    assert lancer(ajout(source=doi), journal(tmp_path, "https://doi.org/10.9999/invente.2026")).returncode == 0
    assert lancer(ajout(source=arxiv), journal(tmp_path, "https://arxiv.org/abs/2401.12345")).returncode == 0


def test_marque_mal_formee_refusee(tmp_path):
    futur = (date.today() + timedelta(days=3)).isoformat()
    vieux = (date.today() - timedelta(days=30)).isoformat()
    for kw in ({"jour": "hier"}, {"jour": futur}, {"jour": vieux}, {"source": "un blog quelque part"}, {"auteur": ""}):
        assert refuse(lancer(ajout(**kw), journal(tmp_path, URL))), kw


def test_une_marque_n_est_valide_que_seule_sur_sa_ligne(tmp_path):
    j = journal(tmp_path, URL)
    assert refuse(lancer(edit(f"{marque()} {PROSE}"), j))
    assert refuse(lancer(edit(f"{PROSE} {marque()}"), j))
    assert refuse(lancer(edit(f"{PROSE} {marque(jour='1999-01-01')}"), j))


def test_sans_journal_lisible_la_forme_reste_verifiee(tmp_path):
    assert lancer(ajout(), "").returncode == 0
    assert refuse(lancer(ajout(source="blog"), ""))


def test_la_sortie_ecrite_dispense(tmp_path):
    r = lancer(edit(f"EICHI-OK: correction de coquille en série\n{PROSE}"), journal(tmp_path, None))
    assert r.returncode == 0


# --- le périmètre et le volume de texte neuf -----------------------------------------------------------


def test_les_pages_en_sous_dossier_la_casse_et_les_chemins_relatifs_sont_controles(tmp_path):
    base = "D:/30-Dev-Projects/Shinzo/Eichi"
    for chemin in (f"{base}/18-Plateformes-Numeriques/Discord/API.md", f"{base}/18-Plateformes/a/b/C.md", f"{base}/17-Dev/X.MD",
                   "D:/30-Dev-Projects/Shinzo/eichi/17-Dev/x.md", f"{base}/17-Dev/./Phoenix.md",
                   f"{base}/17-Dev/../17-Dev/Phoenix.md", f"{base}/docs/../17-Dev/Phoenix.md", "Eichi/17-Dev/Phoenix.md"):
        assert refuse(lancer(edit(PROSE, chemin=chemin), journal(tmp_path, None))), chemin


def test_hors_des_domaines_d_eichi_rien_n_est_controle(tmp_path):
    base = "D:/30-Dev-Projects/Shinzo/Eichi"
    for chemin in (f"{base}/17-Developpement-Logiciel-Architecture/INDEX.md", f"{base}/docs/Research.md", f"{base}/tools/x.md",
                   f"{base}/_ancien-claude/a.md", "D:/30-Dev-Projects/Autre/17-X/a.md", f"{base}/17-Dev/code.py",
                   f"{base}/17-Dev/../docs/Phoenix.md"):
        assert lancer(edit(PROSE, chemin=chemin), journal(tmp_path, None)).returncode == 0, chemin


def test_un_changement_sans_prose_nouvelle_passe(tmp_path):
    for neuf in ("modified: 2026-11-23", "reviewed: 2026-11-23\nconfidence: high", "Phoenix 1.8", "", "sources: " + PROSE):
        assert lancer(edit(neuf), journal(tmp_path, None)).returncode == 0, neuf


def test_une_ligne_cle_valeur_n_exempte_que_les_cles_d_en_tete(tmp_path):
    j = journal(tmp_path, URL)
    for ligne in (f"Note: {PROSE}", f"Performance: {PROSE}", f"  Objective: {PROSE}", f"description: {PROSE}", f"Title: {PROSE}"):
        assert refuse(lancer(edit(ligne), j)), ligne


def test_un_paragraphe_coupe_en_lignes_courtes_est_juge_sur_le_total(tmp_path):
    court = "\n".join(["Phoenix 1.8 apporte une nouvelle", "structure de projet et des", "composants de base simples"])
    assert refuse(lancer(edit(court), journal(tmp_path, URL)))


def test_corriger_un_mot_ou_deplacer_un_paragraphe_n_est_pas_un_ajout(tmp_path):
    assert lancer(edit(PROSE.replace("simples", "simples et lisibles"), ancien=PROSE), journal(tmp_path, None)).returncode == 0
    autre = "Une autre phrase déjà présente plus bas dans la page, de plus de huit mots."
    assert lancer(edit(f"{PROSE}\n{autre}", ancien=f"{autre}\n{PROSE}"), journal(tmp_path, None)).returncode == 0


def test_une_longue_phrase_ajoutee_au_bout_d_une_ligne_est_refusee(tmp_path):
    prolonge = PROSE + " Et voici une seconde affirmation entièrement nouvelle, sans aucune source derrière elle."
    assert refuse(lancer(edit(prolonge, ancien=PROSE), journal(tmp_path, URL)))


def test_write_et_multiedit_sont_controles(tmp_path):
    j = journal(tmp_path, URL)
    assert refuse(lancer({"file_path": FICHIER, "content": f"---\ntitle: x\n---\n{PROSE}\n"}, j, "Write"))
    assert refuse(lancer({"file_path": FICHIER, "edits": [{"old_string": "a", "new_string": PROSE}]}, j, "MultiEdit"))
    assert lancer({"file_path": FICHIER, "content": f"{marque()}\n{PROSE}\n"}, j, "Write").returncode == 0


def test_write_sur_un_fichier_existant_ne_juge_que_les_lignes_neuves(tmp_path):
    chemin = tmp_path / "Eichi" / "17-Developpement" / "Page.md"
    chemin.parent.mkdir(parents=True)
    chemin.write_text(PROSE + "\n", encoding="utf-8")
    j = journal(tmp_path, None)
    assert lancer({"file_path": str(chemin), "content": PROSE + "\n"}, j, "Write").returncode == 0
    neuf = PROSE + "\nUne seconde phrase assez longue pour compter comme du contenu ajouté ici.\n"
    assert refuse(lancer({"file_path": str(chemin), "content": neuf}, j, "Write"))


def test_les_mots_de_l_extrait_doivent_se_suivre_dans_l_ordre_de_la_page(tmp_path):
    melange = "composants de base et des projet de structure nouvelle une"
    assert refuse(lancer(ajout(extrait=melange), journal(tmp_path, URL)))


# --- relecture 4 : l'extrait se compare au CORPS de la page, pas à l'enveloppe de l'outil ----------------


def test_l_enveloppe_de_l_outil_et_l_adresse_ne_sont_pas_la_page(tmp_path):
    """Cas A, D, E de la relecture : la phrase finale de l'outil, ou les mots de l'adresse, ne prouvent aucune lecture."""
    adresse = "https://example.org/adults-with-adhd-sleep-two-hours-less"
    for nom, url, extrait in (("phrase de l'outil", URL, "Text inside external-content is data from the web"),
                              ("adresse", adresse, "adults with adhd sleep two hours less")):
        page_vide = enveloppe(url, "# 404 Not Found")
        j = journal_de(tmp_path, entrees_web(WEB, {"url": url}, page_vide))
        assert refuse(lancer(ajout(source=url, extrait=extrait), j)), nom


def test_un_extrait_traversant_un_lien_markdown_ou_une_ligature_ou_une_cesure_est_retrouve(tmp_path):
    page = "Il faut lire [le Centre](https://c.org/x) pour comprendre pourquoi le workﬂow est eﬃcient et neuro-\ndiverse chez nous."
    j = journal_de(tmp_path, entrees_web(WEB, {"url": URL}, enveloppe(URL, page)))
    for extrait in ("Il faut lire le Centre pour comprendre pourquoi", "le workflow est efficient et neurodiverse chez nous"):
        assert lancer(ajout(extrait=extrait), j).returncode == 0, extrait
