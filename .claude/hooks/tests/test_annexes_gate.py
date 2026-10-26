"""Le garde-fou des annexes : une annexe est lue AVANT le travail qui la requiert.

Pourquoi il existe (Jay, 2026-10-26) : « c'est arrivé trop de fois où l'on a démarré une plateforme,
et le socle minimal n'était pas respecté ». Une règle lue seulement quand on y pense ne tient pas ;
une règle dont l'écriture est bloquée tant qu'elle n'a pas été lue, si.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / ".claude/hooks/lib"))

import annexes  # noqa: E402

GARDE = RACINE / ".claude/hooks/guards/annexes-gate.py"
MANIFESTE = RACINE / ".claude/rules-ondemand/annexes.json"


@pytest.fixture(scope="module")
def registre():
    return annexes.charger(RACINE)


def _ids(registre, outil, chemin="", commande="", existe=True):
    return {a["id"] for a in annexes.requises(registre, outil, chemin, commande, existe)}


# --- le motif de chemin ------------------------------------------------------------------

@pytest.mark.parametrize("motif,chemin,attendu", [
    ("**/docs/CDC.md", "D:/x/projet/docs/CDC.md", True),
    ("**/docs/CDC.md", "docs/CDC.md", True),
    ("**/docs/CDC.md", "D:/x/projet/docs/CDC.md.bak", False),
    ("**/*.tsx", "src/ui/a/b.tsx", True),
    ("**/*.tsx", "src/ui/a/b.ts", False),
    ("**/05-Memoire/**", "D:/Shinzo/05-Memoire/x.md", True),
    ("**/tests/**", "Kata/.claude/hooks/tests/test_a.py", True),
    ("**/test_*.py", "a/b/test_foo.py", True),
])
def test_should_match_a_path_pattern_the_way_it_reads(motif, chemin, attendu):
    assert annexes.correspond_chemin(motif, chemin) is attendu


def test_should_normalise_windows_separators():
    assert annexes.correspond_chemin("**/docs/CDC.md", r"D:\x\projet\docs\CDC.md")


# --- ce que chaque moment exige ----------------------------------------------------------

def test_should_demand_the_minimal_foundation_before_writing_a_cdc(registre):
    assert "socle-minimal" in _ids(registre, "Write", "D:/p/docs/CDC.md")


def test_should_demand_the_minimal_foundation_before_scaffolding_a_project(registre):
    assert "socle-minimal" in _ids(registre, "Bash", commande="pnpm create next-app demo")
    assert "socle-minimal" in _ids(registre, "Bash", commande="mix phx.new shizen")


def test_should_demand_the_foundation_for_a_NEW_manifest_only(registre):
    assert "socle-minimal" in _ids(registre, "Write", "D:/p/package.json", existe=False)
    assert "socle-minimal" not in _ids(registre, "Write", "D:/p/package.json", existe=True)


def test_should_demand_the_interface_annex_before_touching_a_screen(registre):
    assert "interface" in _ids(registre, "Edit", "D:/p/src/Button.tsx")
    assert "interface" in _ids(registre, "Write", "D:/p/docs/Mockups-X.html")
    assert "interface" in _ids(registre, "Edit", "D:/p/src/i18n/fr/common.json")


def test_should_demand_the_tests_annex_before_writing_a_test(registre):
    assert "tests-et-mesures" in _ids(registre, "Write", "D:/p/tests/test_a.py")
    assert "tests-et-mesures" in _ids(registre, "Edit", "D:/p/src/a.test.ts")


def test_should_demand_conventions_for_a_new_source_file_and_for_a_commit(registre):
    assert "conventions-et-pile" in _ids(registre, "Write", "D:/p/src/a.py", existe=False)
    assert "conventions-et-pile" not in _ids(registre, "Edit", "D:/p/src/a.py")
    assert "conventions-et-pile" in _ids(registre, "Bash", commande='git commit -m "x"')


def test_should_demand_the_service_annex_before_a_deployment(registre):
    assert "mise-en-service" in _ids(registre, "Bash", commande="docker compose up -d")
    assert "mise-en-service" in _ids(registre, "Bash", commande="ssh vps 'systemctl restart app'")


def test_should_demand_the_outbound_annex_before_sending_out(registre):
    assert "confidentialite-detail" in _ids(registre, "Bash", commande="gh issue create -t x")
    assert "confidentialite-detail" in _ids(registre, "Bash", commande="curl -X POST https://e.x/a")


def test_should_demand_the_report_annexes_before_writing_a_session_report(registre):
    ids = _ids(registre, "Write", "D:/p/docs/Sessions/Session-2026-10-26-001.md")
    assert {"notation", "reprise-et-contexte", "verite-detail"} <= ids


def test_should_demand_the_memory_format_before_writing_a_memory(registre):
    assert "memoire-format" in _ids(registre, "Write", "D:/Shinzo/05-Memoire/x.md")


def test_should_demand_conduct_and_identity_before_any_first_work(registre):
    for outil, chemin, commande in [("Write", "D:/p/notes.txt", ""), ("Bash", "", "pytest -q")]:
        assert {"conduite", "identite-et-strategie"} <= _ids(registre, outil, chemin, commande)


# --- ce qui ne doit JAMAIS bloquer -------------------------------------------------------

@pytest.mark.parametrize("commande", ["ls -la", "git status", "git log --oneline", "cat a.md", "grep -rn x ."])
def test_should_let_a_read_only_command_through(registre, commande):
    assert _ids(registre, "Bash", commande=commande) == set()


def test_should_let_the_annexes_and_rules_themselves_be_edited(registre):
    assert _ids(registre, "Edit", "D:/Kata/.claude/rules-ondemand/Conduite.md") == set()
    assert _ids(registre, "Edit", "D:/Kata/.claude/rules/03-Qualite.md") == set()


# --- le registre se tient lui-même -------------------------------------------------------

def test_every_annex_in_the_register_exists_and_has_a_trigger_or_a_named_carrier(registre):
    for a in registre:
        assert (RACINE / a["fichier"]).is_file(), a["id"]
        assert a["declencheurs"] or (a.get("porteur") and a.get("limite")), (
            f"{a['id']} : ni déclencheur, ni porteur et limite nommés")


def test_every_annex_file_is_in_the_register():
    inscrits = {Path(a["fichier"]).name for a in annexes.charger(RACINE)}
    presents = {p.name for p in (RACINE / ".claude/rules-ondemand").glob("*.md")}
    # les trois règles à la demande historiques ont leur propre porteur (CLAUDE.md)
    historiques = {"5S.md", "Independent-Review.md", "Rule-Format.md"}
    assert presents - historiques == inscrits


# --- le vrai garde-fou, dans un dépôt factice --------------------------------------------

def _depot(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    cible = tmp_path / ".claude/rules-ondemand"
    cible.mkdir(parents=True)
    shutil.copy(MANIFESTE, cible / "annexes.json")
    return tmp_path


def _transcript(tmp_path: Path, lus: list[str]) -> Path:
    t = tmp_path / "t.jsonl"
    lignes = [json.dumps({"message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": p}}]}}) for p in lus]
    t.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return t


def _lancer(depot: Path, transcript: Path, outil: str, entree: dict, sid: str):
    charge = {"tool_name": outil, "tool_input": entree, "session_id": sid, "transcript_path": str(transcript)}
    return subprocess.run([sys.executable, str(GARDE)], input=json.dumps(charge), capture_output=True,
                          text=True, cwd=depot, encoding="utf-8")


def test_the_gate_blocks_a_cdc_write_until_the_annexes_are_read(tmp_path):
    depot = _depot(tmp_path)
    t = _transcript(tmp_path, [])
    r = _lancer(depot, t, "Write", {"file_path": str(depot / "docs/CDC.md"), "content": "x"}, "s1")
    assert r.returncode == 2
    assert "Socle-Minimal.md" in r.stderr
    assert "RECOVERY" in r.stderr


def test_the_gate_opens_once_the_required_annexes_are_read(tmp_path):
    depot = _depot(tmp_path)
    lus = [str(depot / ".claude/rules-ondemand" / n) for n in
           ("Socle-Minimal.md", "Conduite.md", "Identite-Et-Strategie.md")]
    t = _transcript(tmp_path, lus)
    r = _lancer(depot, t, "Write", {"file_path": str(depot / "docs/CDC.md"), "content": "x"}, "s2")
    assert r.returncode == 0, r.stderr


def test_the_gate_lists_every_missing_annex_at_once(tmp_path):
    depot = _depot(tmp_path)
    t = _transcript(tmp_path, [])
    r = _lancer(depot, t, "Write", {"file_path": str(depot / "docs/CDC.md"), "content": "x"}, "s3")
    for nom in ("Socle-Minimal.md", "Conduite.md", "Identite-Et-Strategie.md"):
        assert nom in r.stderr


def test_the_gate_lets_a_read_only_command_through_even_with_nothing_read(tmp_path):
    depot = _depot(tmp_path)
    t = _transcript(tmp_path, [])
    assert _lancer(depot, t, "Bash", {"command": "git status"}, "s4").returncode == 0


def test_the_gate_never_blocks_when_the_register_is_missing(tmp_path):
    # une sonde de lecture ne doit pas rendre une session impossible: pas de registre, pas de blocage
    (tmp_path / ".git").mkdir()
    t = _transcript(tmp_path, [])
    r = _lancer(tmp_path, t, "Write", {"file_path": str(tmp_path / "a.txt"), "content": "x"}, "s5")
    assert r.returncode == 0


# --- le contournement par Bash: écrire par une redirection n'échappe pas au garde-fou ------------
# Relecture hostile du 2026-10-26: `cat > docs/CDC.md` écrit le cahier des charges sans passer par
# l'outil Write, donc sans déclencher le socle minimal.

def test_should_not_let_a_redirection_hide_the_writing_of_a_cdc(registre):
    assert "socle-minimal" in _ids(registre, "Bash", commande="cat > docs/CDC.md <<'EOF'\nx\nEOF")
    assert "socle-minimal" in _ids(registre, "Bash", commande="echo x >> /p/docs/PET.md")


def test_should_see_a_screen_edited_through_sed_or_tee(registre):
    assert "interface" in _ids(registre, "Bash", commande="sed -i 's/a/b/' src/Button.tsx")
    assert "interface" in _ids(registre, "Bash", commande="echo x | tee src/page.html")


def test_running_a_named_test_file_is_not_writing_it(registre):
    assert "tests-et-mesures" not in _ids(registre, "Bash", commande="python -m pytest tests/test_a.py -q")


@pytest.mark.parametrize("commande", [
    "echo hi > /dev/null", "ls 2>&1", "git log 2>/dev/null", "cat docs/CDC.md", "grep -n x src/Button.tsx",
])
def test_should_still_let_pure_reading_through_even_when_it_names_a_watched_file(registre, commande):
    assert _ids(registre, "Bash", commande=commande) == set()


def test_should_count_a_redirection_to_a_real_file_as_work(registre):
    assert {"conduite", "identite-et-strategie"} <= _ids(registre, "Bash", commande="git log > journal.txt")


# --- on juge les fichiers nommés, pas les mots d'un texte ----------------------------------------
# Faux positif réel du 2026-10-26: un message de commit citait `docs/CDC.md` et le garde-fou l'a pris
# pour une écriture du cahier des charges. Même famille que « mesurer une chose, jamais un mot à son sujet ».

def test_should_not_take_a_path_quoted_in_a_commit_message_for_a_written_file(registre):
    assert "socle-minimal" not in _ids(registre, "Bash", commande='git commit -m "ferme cat > docs/CDC.md"')
    assert "interface" not in _ids(registre, "Bash", commande="git commit -m 'revoir src/Button.tsx'")


def test_should_not_read_the_body_of_a_heredoc_as_named_files(registre):
    commande = "cat > docs/CDC.md <<'EOF'\nvoir src/Button.tsx et tests/test_a.py\nEOF"
    ids = _ids(registre, "Bash", commande=commande)
    assert "socle-minimal" in ids                      # la cible de la redirection compte
    assert "interface" not in ids and "tests-et-mesures" not in ids   # le texte du corps, non


# --- relecture indépendante du 2026-10-26 (verdict FAIL): le déclencheur lisait le texte, pas l'acte ---
# Famille: « déclencheur-lit-le-texte-pas-l'acte ». Il se trompait dans les deux sens: il réclamait une
# annexe à cause de mots écrits dans un texte, et laissait passer des écritures réelles du socle.

@pytest.mark.parametrize("commande", [
    "git commit -m 'note: docker compose up later'",
    'echo "curl -X POST x" > notes.txt',
    "cat > probe.py <<'EOF'\nssh vps 'docker compose up'\ncurl -X POST http://x\nEOF",
])
def test_p1_a_command_mentioned_in_a_text_is_not_a_command_run(registre, commande):
    ids = _ids(registre, "Bash", commande=commande)
    assert "mise-en-service" not in ids and "confidentialite-detail" not in ids


def test_p1_but_a_command_run_through_a_shell_string_still_counts(registre):
    assert "mise-en-service" in _ids(registre, "Bash", commande='bash -c "docker compose up -d"')
    assert "mise-en-service" in _ids(registre, "Bash", commande="ssh vps 'systemctl restart app'")


@pytest.mark.parametrize("commande", [
    "python -c \"open('docs/CDC.md','w').write('x')\"",
    "cd docs && echo x > CDC.md",
    "pnpm dlx create-vite demo",
    "bunx create-next-app demo",
    "django-admin startproject site",
])
def test_p2_the_foundation_cannot_be_dodged_through_bash(registre, commande):
    assert "socle-minimal" in _ids(registre, "Bash", commande=commande)


def test_p2_a_new_manifest_copied_by_bash_is_a_new_project(registre):
    assert "socle-minimal" in _ids(registre, "Bash", commande="cp ../tpl/package.json zzz-nouveau/package.json")


def test_p2_notebook_edit_is_work_too(registre):
    assert {"conduite", "identite-et-strategie"} <= _ids(registre, "NotebookEdit")


@pytest.mark.parametrize("chemin", [
    "D:/p/lib/app_web/components/layouts/app.html.heex",
    "D:/p/lib/kobo_web/live/memories_live.ex",
    "D:/p/priv/gettext/fr/LC_MESSAGES/default.po",
    "D:/p/src/routes/+page.svelte",
    "D:/p/messages/fr.json",
])
def test_p3_the_default_stack_screens_trigger_the_interface_annex(registre, chemin):
    assert "interface" in _ids(registre, "Edit", chemin)


def test_p4_windows_paths_ignore_case(registre):
    assert "socle-minimal" in _ids(registre, "Write", r"D:\x\proj\Docs\cdc.md")


@pytest.mark.parametrize("commande,absent", [
    ("python scripts/check.py", "veille-et-savoir"),
    ("git add docs/CDC.md", "socle-minimal"),
    ("python -m pytest tests/test_a.py -q", "tests-et-mesures"),
])
def test_p5_naming_a_file_is_not_writing_it(registre, commande, absent):
    assert absent not in _ids(registre, "Bash", commande=commande)


def _depot_agent(tmp_path, lus, agent):
    (tmp_path / ".git").mkdir()
    cible = tmp_path / ".claude/rules-ondemand"
    cible.mkdir(parents=True)
    shutil.copy(MANIFESTE, cible / "annexes.json")
    parent = tmp_path / "t.jsonl"
    parent.write_text("", encoding="utf-8")
    if lus is not None:
        propre = tmp_path / "t" / "subagents"
        propre.mkdir(parents=True)
        lignes = [json.dumps({"message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": str(cible / n)}}]}}) for n in lus]
        (propre / f"agent-{agent}.jsonl").write_text("\n".join(lignes) + "\n", encoding="utf-8")
    charge = {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "n.txt"), "content": "x"},
              "session_id": "S-" + agent, "transcript_path": str(parent), "agent_id": agent}
    return subprocess.run([sys.executable, str(GARDE)], input=json.dumps(charge), capture_output=True,
                          text=True, cwd=tmp_path, encoding="utf-8")


def test_s1_a_sub_agent_is_judged_on_its_own_journal():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _depot_agent(Path(d), ["Conduite.md", "Identite-Et-Strategie.md"], "abc123")
        assert r.returncode == 0, r.stderr


def test_s1_a_sub_agent_that_read_nothing_is_still_asked():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        assert _depot_agent(Path(d), [], "abc124").returncode == 2


def test_s1_a_sub_agent_without_a_readable_journal_is_never_blocked():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        assert _depot_agent(Path(d), None, "zzz").returncode == 0


# --- changement de méthode (2026-10-26, après deux FAIL de même famille): la commande est LUE, pas cherchée ---
# Chaque cas vient d'une commande réelle prouvée par l'un des deux relecteurs; voir `test_actes.py` pour le
# découpage lui-même. Ici: ce que le registre exige ensuite.

@pytest.mark.parametrize("commande", [
    'cp tpl.md "docs/CDC.md"',
    "echo x > 'docs/CDC.md'",
    'cp tpl.md "D:/x/my proj/docs/CDC.md"',
    "uv run python -c \"open('docs/CDC.md','w')\"",
    "py -c \"open('docs/CDC.md','w').write('x')\"",
    "env X=1 bash -c 'cp a docs/CDC.md'",
    "perl -e 'open(F,\">docs/CDC.md\")'",
    "cat a.txt | xargs sh -c 'cp \"$0\" docs/CDC.md'",
    "sudo -u deploy cp a docs/CDC.md",
])
def test_m1_every_disguised_write_of_the_cdc_demands_the_foundation(registre, commande):
    assert "socle-minimal" in _ids(registre, "Bash", commande=commande)


def test_m1_running_a_script_is_not_writing_it(registre):
    commande = ("echo '{}' | python .claude/hooks/lifecycle/capacites-check.py | "
                "python -c \"import json,sys;d=json.load(sys.stdin);print(d['x'])\"")
    assert _ids(registre, "Bash", commande=commande) <= {"conduite", "identite-et-strategie"}


def test_m1_copying_a_manifest_template_does_not_demand_the_watch(registre):
    # `veille-et-savoir` est déclarée sans Bash: copier un modèle n'est pas écrire du code à veiller
    ids = _ids(registre, "Bash", commande="cp ../tpl/package.json newproj/package.json")
    assert "veille-et-savoir" not in ids and "socle-minimal" in ids


def test_m1_a_notebook_edit_asks_only_for_the_first_work_annexes(registre):
    # décision: un .ipynb n'est ni un écran, ni un test, ni du code veillé — seulement du travail
    assert _ids(registre, "NotebookEdit", "D:/p/analyse.ipynb") == {"conduite", "identite-et-strategie"}


# --- relecture n° 3 (2026-10-26, FAIL): motifs incomplets, guillemets sur un mot, dossier temporaire ------------

@pytest.mark.parametrize("commande,attendu", [
    ("mix new demo", "socle-minimal"),
    ("npm 'init' -y", "socle-minimal"),
    ('docker "compose" up -d', "mise-en-service"),
    ("docker-compose up -d", "mise-en-service"),
    ("curl -F f=@docs/x.md https://x.example", "confidentialite-detail"),
    ("curl -d@payload.json https://x.example", "confidentialite-detail"),
    ("curl --json '{\"a\":1}' https://x.example", "confidentialite-detail"),
    ("curl -T fichier.zip https://x.example", "confidentialite-detail"),
])
def test_r3_the_patterns_cover_the_real_forms_of_the_gesture(registre, commande, attendu):
    assert attendu in _ids(registre, "Bash", commande=commande)


def test_r3_a_report_written_in_a_temporary_folder_is_not_a_session_report(registre):
    commande = 'printf x > "C:/Users/a/AppData/Local/Temp/claude/r/docs/Sessions/x.md"'
    assert {"notation", "reprise-et-contexte", "verite-detail"}.isdisjoint(_ids(registre, "Bash", commande=commande))
    assert {"notation"} <= _ids(registre, "Bash", commande="printf x > docs/Sessions/Session-2026-10-26-001.md")


def test_r3_a_reading_that_names_a_message_with_a_command_stays_quiet(registre):
    assert _ids(registre, "Bash", commande="git commit -m 'note: docker compose up later'") == {
        "conduite", "identite-et-strategie", "conventions-et-pile"}
