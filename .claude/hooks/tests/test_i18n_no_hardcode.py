"""lego/i18n-no-hardcode.py — le texte en dur BLOQUE là où le projet a une bibliotheque de traduction (2026-10-30).

Mesure du jour : 362 fichiers sur 3 695 portent du texte en dur sans traduction, malgre un avertissement
(qui, de plus, n'atteignait pas le modele). Un projet sans aucune bibliotheque installee garde l'avertissement :
y bloquer toute edition d'interface la rendrait impossible et ferait debrancher le garde.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "lego" / "i18n-no-hardcode.py"
TEXTE = "export function Carte() {\n  return <p>Bienvenue, ton espace est prêt à l'emploi !</p>;\n}\n"


def _projet(tmp_path: Path, dependances: dict | None = None, dev: dict | None = None) -> Path:
    (tmp_path / ".git").mkdir()
    manifest = {"name": "demo", "dependencies": dependances or {}, "devDependencies": dev or {}}
    (tmp_path / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "src").mkdir()
    return tmp_path


def _lancer(chemin: Path, contenu: str, outil: str = "Write") -> subprocess.CompletedProcess:
    cle = "content" if outil == "Write" else "new_string"
    entree = {"hook_event_name": "PreToolUse", "tool_name": outil,
              "tool_input": {"file_path": str(chemin).replace("\\", "/"), cle: contenu}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(entree), capture_output=True, text=True,
                          timeout=30)


def test_blocks_hardcoded_text_in_a_project_that_has_an_i18n_library(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "^4"})
    sortie = _lancer(projet / "src" / "Carte.tsx", TEXTE)
    assert sortie.returncode == 2 and "I18N-OK" in sortie.stderr and sortie.stdout.strip() == ""


def test_every_known_i18n_library_counts_including_dev_dependencies(tmp_path):
    cas = [("shinkofa", {"@shinkofa/i18n": "1"}, None), ("react", {"react-i18next": "1"}, None),
           ("core", {"i18next": "1"}, None), ("dev", None, {"next-intl": "1"})]
    for nom, dependances, dev in cas:
        dossier = tmp_path / nom
        dossier.mkdir()
        projet = _projet(dossier, dependances, dev)
        assert _lancer(projet / "src" / "Carte.tsx", TEXTE).returncode == 2, nom


def test_a_project_without_a_library_is_warned_not_blocked(tmp_path):
    projet = _projet(tmp_path, {"react": "19"})
    sortie = _lancer(projet / "src" / "Carte.tsx", TEXTE)
    assert sortie.returncode == 0
    assert "hardcoded UI text" in json.loads(sortie.stdout)["hookSpecificOutput"]["additionalContext"]


def test_a_monorepo_workspace_inherits_the_root_library(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    (projet / "apps" / "web" / "src").mkdir(parents=True)
    (projet / "apps" / "web" / "package.json").write_text('{"name": "web"}', encoding="utf-8")
    assert _lancer(projet / "apps" / "web" / "src" / "Carte.tsx", TEXTE).returncode == 2


def test_a_closed_motif_lets_it_through_as_a_comment(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    for motif in ("internal-tool", "editorial-content", "already-translated"):
        for forme in (f"// I18N-OK: {motif}\n", f"{{/* I18N-OK: {motif} */}}\n"):
            assert _lancer(projet / "src" / "Carte.tsx", forme + TEXTE).returncode == 0, (motif, forme)


def test_an_open_motif_or_a_mere_mention_does_not_let_it_through(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    for ligne in ("// I18N-OK: pas le temps\n", "const doc = 'I18N-OK: internal-tool';\n"):
        assert _lancer(projet / "src" / "Carte.tsx", ligne + TEXTE).returncode == 2, ligne


def test_an_edit_is_cleared_by_the_motif_already_written_in_the_file(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    fichier = projet / "src" / "Admin.tsx"
    fichier.write_text("// I18N-OK: internal-tool\n" + TEXTE, encoding="utf-8")
    assert _lancer(fichier, "<p>Un autre texte en dur ici present</p>", outil="Edit").returncode == 0
    autre = projet / "src" / "Public.tsx"
    autre.write_text(TEXTE, encoding="utf-8")
    assert _lancer(autre, "<p>Un autre texte en dur ici present</p>", outil="Edit").returncode == 2


def test_translated_text_passes(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    contenu = "export function Carte() {\n  const t = useTranslations('carte');\n  return <p>{t('titre')}</p>;\n}\n"
    assert _lancer(projet / "src" / "Carte.tsx", contenu).returncode == 0


def test_one_raw_sentence_in_a_file_that_already_translates_is_still_blocked(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    contenu = ("const t = useTranslations('carte');\n"
               "export const A = () => <h1>{t('titre')}</h1>;\n"
               "export const B = () => <p>Bienvenue sur ton espace personnel</p>;\n")
    assert _lancer(projet / "src" / "Carte.tsx", contenu).returncode == 2


def test_code_that_merely_contains_comparison_signs_is_not_text(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    contenu = ("export function Carte({ count, limit }) {\n"
               "  const ok = count > limit && count < limit * 2 && limit > count;\n"
               "  return <p className=\"x\">{ok ? 'a' : 'b'}</p>;\n}\n")
    assert _lancer(projet / "src" / "Carte.tsx", contenu).returncode == 0


def test_tests_stories_and_vendored_files_are_skipped(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    for nom in ("src/Carte.test.tsx", "src/Carte.stories.tsx", "src/__tests__/Carte.tsx", "node_modules/x/Carte.tsx"):
        assert _lancer(projet / nom, TEXTE).returncode == 0, nom


def test_a_file_that_is_not_ui_is_ignored(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    assert _lancer(projet / "src" / "lib.ts", TEXTE).returncode == 0


# --- faux positifs vus sur de vrais fichiers (9 depots, 2026-10-30) : du code lu comme du texte ----------------

_CODE_FAUX_POSITIFS = {
    "generics": "export function A() {\n  const [rows, setRows] = useState<Row[]>([]);\n"
                "  const [current, setCurrent] = useState<string | null>(null);\n  return <p className=\"x\" />;\n}\n",
    "self-closing": "export const A = () => (\n  <Foo bar=\"1\" />\n  // Score without max show as text\n  <Bar />\n);\n",
    "record type": "type P = { palette: Record<string, string>; items: Array<number> | null; label: string };\n",
    "assignment text": "const x = <p>total = a + b ; resultat final ici</p>;\n",
    "title variable": "const title = \"Mon super titre ici present\";\nconst place = placeholder = 'Une valeur par defaut';\n",
}


def test_typescript_code_is_not_read_as_interface_text(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    for nom, code in _CODE_FAUX_POSITIFS.items():
        assert _lancer(projet / "src" / "Carte.tsx", code).returncode == 0, nom


def test_a_mockup_file_is_skipped(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    for nom in ("src/mock-scouting.tsx", "src/mocks/Carte.tsx", "src/mockups/Carte.tsx"):
        assert _lancer(projet / nom, TEXTE).returncode == 0, nom


def test_text_after_an_opening_tag_with_attributes_is_still_caught(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    contenu = "export const A = () => <p className=\"intro\" id=\"a\">Le joueur est une personne, pas un pseudo.</p>;\n"
    assert _lancer(projet / "src" / "Carte.tsx", contenu).returncode == 2
    attribut = "export const B = () => <Input placeholder=\"Ton adresse e-mail ici\" />;\n"
    assert _lancer(projet / "src" / "Carte.tsx", attribut).returncode == 2


# --- relecture independante du 2026-10-30 -------------------------------------------------------------------

def _lancer_modif(chemin: Path, edits: list[tuple[str, str]], outil: str = "Edit") -> subprocess.CompletedProcess:
    cible = str(chemin).replace("\\", "/")
    if outil == "Edit":
        entree_outil = {"file_path": cible, "old_string": edits[0][0], "new_string": edits[0][1]}
    else:
        entree_outil = {"file_path": cible, "edits": [{"old_string": a, "new_string": n} for a, n in edits]}
    entree = {"hook_event_name": "PreToolUse", "tool_name": outil, "tool_input": entree_outil}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(entree), capture_output=True, text=True,
                          timeout=30)


def test_an_edit_that_leaves_the_text_alone_is_not_blocked(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    ancien = '<p className="a">Bienvenue dans ton espace</p>'
    nouveau = '<p className="b">Bienvenue dans ton espace</p>'
    assert _lancer_modif(projet / "src" / "Carte.tsx", [(ancien, nouveau)]).returncode == 0
    ajoute = '<p className="b">Bienvenue dans ton espace, cher visiteur</p>'
    assert _lancer_modif(projet / "src" / "Carte.tsx", [(ancien, ajoute)]).returncode == 2


def test_a_multiedit_is_read_like_an_edit(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    chemin = projet / "src" / "Carte.tsx"
    assert _lancer_modif(chemin, [("<b>x</b>", "<p>Bienvenue dans ton espace perso</p>")], outil="MultiEdit").returncode == 2
    garde = '<p className="a">Bienvenue dans ton espace</p>'
    assert _lancer_modif(chemin, [(garde, garde.replace('"a"', '"b"'))], outil="MultiEdit").returncode == 0


def test_a_multiedit_that_moves_existing_text_adds_nothing(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    chemin = projet / "src" / "Carte.tsx"
    texte = "<p>Bienvenue dans ton espace</p>"
    deplacement = [(texte, "<hr/>"), ('<hr id="2"/>', texte)]
    assert _lancer_modif(chemin, deplacement, outil="MultiEdit").returncode == 0
    neuf = [(texte, "<hr/>"), ('<hr id="2"/>', "<p>Un tout autre texte ici present</p>")]
    assert _lancer_modif(chemin, neuf, outil="MultiEdit").returncode == 2


def test_text_with_a_variable_inside_is_still_text(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    contenu = "export const A = ({ name }) => <p>Bonjour {name}, bienvenue dans ton espace</p>;\n"
    assert _lancer(projet / "src" / "Carte.tsx", contenu).returncode == 2


def test_text_with_an_html_entity_is_still_text(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    contenu = "export const A = () => <p>Bienvenue&nbsp;dans ton espace perso</p>;\n"
    assert _lancer(projet / "src" / "Carte.tsx", contenu).returncode == 2


def test_only_translated_expressions_in_a_tag_are_not_text(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    contenu = "export const A = () => <p>{t('a.titre')} {t('a.suite')} {name}</p>;\n"
    assert _lancer(projet / "src" / "Carte.tsx", contenu).returncode == 0


def test_the_other_common_i18n_libraries_count(tmp_path):
    for nom, dependances in (("intl", {"react-intl": "7"}), ("lingui", {"@lingui/core": "5"}),
                             ("nexti", {"next-i18next": "15"})):
        dossier = tmp_path / nom
        dossier.mkdir()
        projet = _projet(dossier, dependances)
        assert _lancer(projet / "src" / "Carte.tsx", TEXTE).returncode == 2, nom


def test_the_refusal_says_what_to_do_and_names_the_motifs(tmp_path):
    projet = _projet(tmp_path, {"next-intl": "4"})
    message = _lancer(projet / "src" / "Carte.tsx", TEXTE).stderr
    assert "RECOVERY" in message and "internal-tool" in message and "useTranslation" in message
