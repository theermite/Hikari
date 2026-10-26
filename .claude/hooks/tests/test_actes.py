"""Le découpage d'une commande en actes: on juge ce que la commande FAIT, pas ce qu'elle DIT.

Deux relectures indépendantes (2026-10-26) ont rendu FAIL, de la même famille: « le déclencheur lit le
texte d'une commande, pas son acte ». Chaque cas ci-dessous vient d'une commande réelle que l'un des
relecteurs a prouvée. Règle 03 § 6: au deuxième échec de la même famille, changer de méthode — on découpe
la commande (guillemets, séparateurs, enveloppes, sous-commandes), on n'ajoute pas une expression régulière.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / ".claude/hooks/lib"))

import actes  # noqa: E402


def _ecrits(commande: str) -> list[str]:
    return actes.chemins_ecrits(commande)


# --- ce qui ÉCRIT, même déguisé ----------------------------------------------------------------

@pytest.mark.parametrize("commande,attendu", [
    ('cp tpl.md "docs/CDC.md"', "docs/CDC.md"),
    ("echo x > 'docs/CDC.md'", "docs/CDC.md"),
    ('cp tpl.md "D:/x/my proj/docs/CDC.md"', "D:/x/my proj/docs/CDC.md"),
    ("uv run python -c \"open('docs/CDC.md','w')\"", "docs/CDC.md"),
    ("py -c \"open('docs/CDC.md','w').write('x')\"", "docs/CDC.md"),
    ("env X=1 bash -c 'cp a docs/CDC.md'", "docs/CDC.md"),
    ("perl -e 'open(F,\">docs/CDC.md\")'", "docs/CDC.md"),
    ("cat a.txt | xargs sh -c 'cp \"$0\" docs/CDC.md'", "docs/CDC.md"),
    ("cd docs && echo x > CDC.md", "docs/CDC.md"),
    ("(cd docs && echo x > CDC.md)", "docs/CDC.md"),
    ("sudo -u deploy cp a docs/CDC.md", "docs/CDC.md"),
    ("command cp a docs/CDC.md", "docs/CDC.md"),
    ("echo $(cp a docs/CDC.md)", "docs/CDC.md"),
    ("find . -name x -exec cp {} docs/CDC.md \\;", "docs/CDC.md"),
    ("cp CDC.md docs/", "docs/CDC.md"),
    ("sed -i 's/a/b/' src/Button.tsx", "src/Button.tsx"),
    ("echo x | tee src/page.html", "src/page.html"),
    ("git -C . mv a docs/CDC.md", "docs/CDC.md"),
    ("curl -o out/page.html https://e.x/a", "out/page.html"),
    ("cd 'dir with space' && echo x > a.md", "dir with space/a.md"),
])
def test_should_see_the_file_a_command_really_writes(commande, attendu):
    assert attendu in _ecrits(commande)


# --- ce qui NOMME un fichier sans l'écrire -----------------------------------------------------

@pytest.mark.parametrize("commande", [
    "python scripts/check.py",
    "python -m pytest tests/test_a.py -q",
    "git add docs/CDC.md",
    'git commit -m "ferme cat > docs/CDC.md"',
    "cat docs/CDC.md",
    "grep -n x src/Button.tsx",
    "echo hi > /dev/null",
    "ls 2>&1",
    "git log 2>/dev/null",
    "echo '{}' | python .claude/hooks/lifecycle/capacites-check.py | python -c "
    "\"import json,sys;d=json.load(sys.stdin);print(d['x'])\"",
])
def test_should_not_take_a_named_file_for_a_written_file(commande):
    assert _ecrits(commande) == []


def test_the_body_of_a_heredoc_is_data_but_its_target_is_written():
    commande = "cat > probe.py <<'EOF'\nssh vps 'docker compose up'\ncp a docs/CDC.md\nEOF"
    assert _ecrits(commande) == ["probe.py"]


def test_a_heredoc_given_to_a_shell_is_a_command():
    assert "docs/CDC.md" in _ecrits("bash <<'EOF'\ncp a docs/CDC.md\nEOF")


def test_a_commit_message_built_by_substitution_is_still_a_commit():
    commande = "git commit -m \"$(cat <<'EOF'\nfix: ferme :) puis cp a docs/CDC.md\nEOF\n)\""
    assert _ecrits(commande) == []
    assert actes.touche_etat_partage(commande)


# --- lecture seule: une liste FERMÉE de formes acceptées ----------------------------------------

@pytest.mark.parametrize("commande", [
    "ls -la", "git status", "git log --oneline", "cat a.md", "grep -rn x .", "pwd",
    "git -C . status", "git --no-pager log -3", "cd x && ls | wc -l", "git branch", "git branch -a",
    "git remote -v", "git fetch", "git stash list", "git worktree list", "git diff HEAD~1",
    "echo 'cp a docs/CDC.md'", "git rev-parse HEAD", "",
])
def test_should_recognise_a_read_only_command(commande):
    assert actes.est_lecture(commande) is True


@pytest.mark.parametrize("commande", [
    "git pull", "git -C . commit -m x", "git ci -m x", "git branch -D old", "git branch nouvelle",
    "git branch -m a b", "git worktree add ../w", "git stash", "git push", "git tag v1",
    "find . -name x -delete", "find . -name x -exec rm {} \\;", "echo x > f", "ls; rm a",
    "python x.py", "ls $(rm a)", 'bash -c "ls"', "ssh vps ls", "cat a | bash", "git unknowncmd",
    "ls `rm a`", "curl https://e.x", "make",
])
def test_should_not_take_an_acting_command_for_a_reading_one(commande):
    assert actes.est_lecture(commande) is False


# --- l'état partagé: git lu après ses options, sous-commande inconnue = partagé -------------------

@pytest.mark.parametrize("commande", [
    "git pull", "git -C . commit -m x", "git -c user.name=x commit -m y", "git ci -m x",
    "git branch -D old", "git branch -m a b", "git worktree add ../w", "git stash", "git push origin main",
    "bash -c 'git commit -m x'", "env X=1 git reset --hard", "git --git-dir=.git --work-tree=. checkout x",
    "cd x && git commit -m y", "git --no-pager -C . merge x",
    "python scripts/propagate-methodology.py --all-projects --apply",
    "git add a && git commit -m x", "sudo git -C /srv/app pull",
])
def test_should_see_a_gesture_that_changes_what_another_session_uses(commande):
    assert actes.touche_etat_partage(commande) is True


@pytest.mark.parametrize("commande", [
    "git status", "git log", "git diff", "git add a", "git fetch", 'echo "git commit"',
    'git log --grep="git commit"', "git branch", "git branch -a", "git stash list", "git worktree list",
    "python scripts/propagate-methodology.py --all-projects", "git remote -v", "git -C . status",
    "git show HEAD",
])
def test_should_not_take_a_harmless_gesture_for_a_shared_one(commande):
    assert actes.touche_etat_partage(commande) is False


# --- le texte sur lequel les déclencheurs de commande s'appliquent --------------------------------

def test_a_text_inside_a_message_is_not_a_command():
    textes = " | ".join(actes.textes("git commit -m 'note: docker compose up later'"))
    assert "docker" not in textes and "git commit" in textes


def test_a_command_run_through_a_remote_shell_stays_visible():
    assert any("ssh vps systemctl restart app" in t for t in actes.textes("ssh vps 'systemctl restart app'"))
    assert any("docker compose up" in t for t in actes.textes('bash -c "docker compose up -d"'))


def test_git_global_options_do_not_hide_the_subcommand_from_a_pattern():
    assert any(t.startswith("git commit") for t in actes.textes("git -C . -c a=b commit -m x"))


def test_a_malformed_command_never_raises():
    for commande in ["echo 'ouvert", 'echo "ouvert', "$(", "a ||| b", "`", "\\", "<<", "x <<EOF"]:
        actes.est_lecture(commande)
        actes.chemins_ecrits(commande)
        actes.touche_etat_partage(commande)


# --- relecture n° 3 (2026-10-26, FAIL): des tables incomplètes, un verrou qui compte tout comme écriture ----
# Chaque cas a été rejoué avant d'agir. Les constats qui n'ont pas été suivis sont écrits dans l'en-tête de actes.py.

@pytest.mark.parametrize("commande,attendu", [
    ('pwsh -Command "Set-Content docs/CDC.md x"', "docs/CDC.md"),
    ('pwsh -NoProfile -Command "Out-File -FilePath docs\\CDC.md"', "docs/CDC.md"),
    ('powershell -Com "Set-Content docs/CDC.md x"', "docs/CDC.md"),
    ("git diff --output=docs/CDC.md HEAD~1", "docs/CDC.md"),
    ("sort -o docs/CDC.md x", "docs/CDC.md"),
    ("perl -pi -e 's/a/b/' docs/CDC.md", "docs/CDC.md"),
    ("python -Ic \"open('docs/CDC.md','w')\"", "docs/CDC.md"),
    ("node --eval=\"require('fs').writeFileSync('docs/CDC.md','')\"", "docs/CDC.md"),
    ("elixir -e 'File.write!(\"docs/CDC.md\",\"\")'", "docs/CDC.md"),
    ("git checkout HEAD~1 -- docs/CDC.md", "docs/CDC.md"),
    ("git restore -s HEAD~1 docs/CDC.md", "docs/CDC.md"),
])
def test_r3_a_write_hidden_behind_an_option_form_or_an_interpreter_is_seen(commande, attendu):
    assert attendu in _ecrits(commande)


def test_r3_a_source_revision_is_not_a_written_path():
    assert "HEAD~1" not in _ecrits("git restore -s HEAD~1 docs/CDC.md")


@pytest.mark.parametrize("commande", [
    "rg --pre ./x.sh foo", "tree -o docs/CDC.md", "less -o docs/CDC.md README.md",
])
def test_r3_a_reader_that_can_write_or_run_something_is_not_a_reading(commande):
    assert actes.est_lecture(commande) is False


def test_r3_time_with_an_option_still_shows_the_program():
    assert actes.touche_etat_partage("time -p git commit -m x") is True


@pytest.mark.parametrize("commande", [
    "git reflog -5", "git branch --contains HEAD", "git branch --merged", "git tag --sort=-v:refname",
    "git cherry -v", "git tag -l 'v*'", "git branch --no-merged main",
])
def test_r3_a_git_reading_with_an_option_is_not_a_shared_gesture(commande):
    assert actes.touche_etat_partage(commande) is False
    assert actes.est_lecture(commande) is True


def test_r3_a_remote_gesture_is_not_a_local_one():
    # `ssh vps "cd /srv/app && git pull"` met le serveur à jour: ça ne change ni l'arbre ni la branche d'ici
    assert actes.touche_etat_partage('ssh vps "cd /srv/app && git pull"') is False
    assert "/srv/docs/CDC.md" not in _ecrits("ssh vps 'echo x > /srv/docs/CDC.md'")
    assert any("git pull" in t for t in actes.textes('ssh vps "cd /srv/app && git pull"'))


@pytest.mark.parametrize("commande", [
    "pytest -q", "cd web && pnpm test", "docker compose logs api", "npx vitest run",
])
def test_r3_running_something_is_not_writing_something(commande):
    assert actes.ecrit(commande) is False


@pytest.mark.parametrize("commande", [
    "echo x > f", "git commit -m x", "cp a b", "sed -i s/a/b/ f", "bash -c 'touch f'",
])
def test_r3_a_real_write_or_shared_gesture_counts_as_writing(commande):
    assert actes.ecrit(commande) is True


def test_r3_a_quoted_single_word_is_still_a_command_word():
    assert any(t.startswith("npm init") for t in actes.textes("npm 'init' -y"))
    assert any(t.startswith("docker compose up") for t in actes.textes('docker "compose" up -d'))
    assert "docker" not in " ".join(actes.textes("git commit -m 'note: docker compose up later'"))


def test_r3_an_unresolved_variable_is_not_a_path():
    assert _ecrits('printf x > "$D/r/docs/Sessions/x.md"') == []


def test_r3_a_comment_is_read_as_a_comment_not_as_a_text():
    assert actes.commentaires("git commit -m 'a # WRITER-OK: b' # WRITER-OK: c") == ["# WRITER-OK: c"]
    assert actes.commentaires("echo a#b") == []


def test_r3_powershell_command_with_args_is_code_too():
    # learn.microsoft.com/powershell/.../about_pwsh (consulté le 2026-10-26): -Command | -c, -CommandWithArgs | -cwa,
    # paramètres insensibles à la casse
    assert "docs/CDC.md" in _ecrits('pwsh -CWA "Set-Content docs/CDC.md x"')
    assert "docs/CDC.md" in _ecrits('POWERSHELL -C "Set-Content docs/CDC.md x"')


# --- relecture n° 4 (2026-10-26, FAIL): le verrou avait inversé le sens de l'erreur --------------------------
# Compter « seulement les écrivains connus » laissait passer formateurs et gestionnaires de paquets. Le sens
# voulu: une liste FERMÉE d'inoffensifs (lectures, tests, vérifications); tout le reste compte comme écriture.

@pytest.mark.parametrize("commande", [
    "npx prettier --write src/", "npx eslint --fix .", "ruff format .", "black .", "mix format", "cargo fmt",
    "pnpm add react", "cargo add serde", "uv add httpx", "mix ecto.gen.migration add_users",
    "python manage.py makemigrations", "npx shadcn@latest add button", "pnpm install",
])
def test_r4_whatever_can_rewrite_files_counts_as_writing(commande):
    assert actes.ecrit(commande) is True


@pytest.mark.parametrize("commande", [
    "pytest -q", "python -m pytest tests -q", "pnpm test", "npm run test", "cd web && pnpm test", "npx vitest run",
    "mix test", "cargo test", "go test ./...", "docker compose logs api", "docker compose ps", "docker logs app",
    "ssh vps 'docker ps'", "ssh vps 'cd /srv/app && git pull'",
    'curl -sf -o /dev/null -w "%{http_code}" http://localhost:3000/health', "npm test 2>nul", "pytest > NUL",
    "git status", "ls",
])
def test_r4_a_known_harmless_command_does_not_count_as_writing(commande):
    assert actes.ecrit(commande) is False


@pytest.mark.parametrize("commande", ["git branch --list 'feat*'", "git branch -l 'feat*'", "git branch -a"])
def test_r4_listing_branches_by_pattern_is_a_reading(commande):
    assert actes.touche_etat_partage(commande) is False and actes.est_lecture(commande) is True


@pytest.mark.parametrize("commande", ["npm version patch", "pnpm version minor", "yarn version"])
def test_r4_a_version_bump_commits_and_tags(commande):
    assert actes.touche_etat_partage(commande) is True
    assert actes.touche_etat_partage("npm version patch --no-git-tag-version") is False


@pytest.mark.parametrize("commande", ["git checkout HEAD~1 docs/CDC.md", "git checkout docs/CDC.md"])
def test_r4_checkout_of_a_file_without_double_dash_writes_it(commande):
    assert "docs/CDC.md" in _ecrits(commande)
    assert _ecrits("git checkout -b feature/x") == [] and _ecrits("git checkout main") == []


# --- relecture n° 5 (2026-10-26, FAIL en sens contraire de la n° 4): deux niveaux au lieu d'une liste ----------
# Une seule liste fermée ne peut pas satisfaire deux erreurs de coût différent: une écriture non vue laisse un
# commit embarquer le travail d'autrui; une lecture prise pour une écriture REFUSE le commit de l'autre séance.
# `ecrit` = certain (peut bloquer); `peut_ecrire` = certain ou inconnu (avertit seulement).

@pytest.mark.parametrize("commande", ["make", "python build_site.py", "./deploy.sh", "gh pr view 3", "pnpm build"])
def test_r5_an_unknown_command_may_write_but_is_never_certain(commande):
    assert actes.peut_ecrire(commande) is True
    assert actes.ecrit(commande) is False


@pytest.mark.parametrize("commande", [
    "npx prettier --write src/", "pnpm exec prettier --write .", "ruff format .", "black src", "mix format",
    "cargo fmt", "pnpm add react", "npm install", "uv add httpx", "mix deps.get",
    "npx shadcn@latest add button", "ruff check --fix .", "npx eslint --fix .",
])
def test_r5_a_known_rewriter_is_a_certain_write(commande):
    assert actes.ecrit(commande) is True and actes.peut_ecrire(commande) is True


@pytest.mark.parametrize("commande", [
    "ruff format --check .", "black --check .", "mix format --check-formatted", "cargo fmt --check",
    "npx prettier --check .", "npm run test", "pnpm test", "ruff check .", "pnpm list",
])
def test_r5_checking_is_not_rewriting(commande):
    assert actes.ecrit(commande) is False


@pytest.mark.parametrize("commande", [
    "python -I -m pytest -q", "python -m ruff check .", "python -m mypy .", "tsc --noEmit", "npx tsc --noEmit",
    "mypy .", "sed -n 1,5p README.md", "sort a | head",
])
def test_r5_common_readings_and_checks_are_not_even_possible_writes(commande):
    assert actes.peut_ecrire(commande) is False


# --- relecture n° 6 (2026-10-26, FAIL): faux « certain » sur des lectures, vérifications et installations ------
# Un faux « certain » refuse à tort le commit de l'autre séance: seul ce qui réécrit un fichier SUIVI l'est.
# Installer dans node_modules / .venv / site-packages n'écrit aucun fichier suivi: c'est « possible », pas certain.

@pytest.mark.parametrize("commande", [
    "uv pip list", "uv pip freeze", "uv pip show ruff", "uv pip install httpx", "pip install -r requirements.txt",
    "pip install -e .", "npm ci", "pnpm install --frozen-lockfile", "yarn install --immutable", "uv sync --locked",
    "uv sync --frozen", "isort --check-only .", "isort -c .", "gofmt -l .", "gofmt -d .", "autopep8 x.py",
    "poetry lock --check", "npm run format:check", "pnpm run format --check", "npm run test:fixtures",
    "npm run prefixes", "ruff check --fix --diff .", "black --diff .",
])
def test_r6_what_does_not_rewrite_a_tracked_file_is_not_a_certain_write(commande):
    assert actes.ecrit(commande) is False


@pytest.mark.parametrize("commande", [
    "npm install", "pnpm install", "uv sync", "uv add httpx", "gofmt -w .", "autopep8 -i x.py", "isort .",
    "npm run format", "pnpm run fix", "npm run lint:fix", "cargo clippy --fix", "poetry lock", "ruff check --fix .",
])
def test_r6_what_rewrites_a_tracked_file_is_still_a_certain_write(commande):
    assert actes.ecrit(commande) is True


def test_r6_tsc_without_no_emit_may_write_and_python_dash_m_must_come_before_the_script():
    assert actes.peut_ecrire("tsc --noEmit") is False and actes.peut_ecrire("tsc") is True
    assert actes.peut_ecrire("python scripts/gen.py -m pytest") is True


# --- relecture n° 7 (2026-10-26, FAIL): écrire HORS du dépôt n'écrit aucun fichier suivi ------------------------

RACINE_DEPOT = "D:/30-Dev-Projects/Kata"


@pytest.mark.parametrize("commande", [
    "pytest -q > /tmp/out.txt", "pytest -q > C:/Users/jaygo/AppData/Local/Temp/x.txt", "git diff > /tmp/patch.diff",
    "scp dist.tar.gz vps:/tmp/", "echo x > ~/notes.txt", "cp a.txt /d/autre-projet/a.txt",
    "echo x > /d/30-Dev-Projects/Autre/a.txt",
])
def test_r7_a_write_outside_the_repository_is_not_a_certain_write_of_it(commande):
    assert actes.ecrit(commande, RACINE_DEPOT) is False


@pytest.mark.parametrize("commande", [
    "echo x > f.txt", "cp a b", "echo x > D:/30-Dev-Projects/Kata/docs/a.md", "echo x > /d/30-Dev-Projects/Kata/a.md",
    "cd docs && echo x > a.md", "sed -i s/a/b/ src/x.py",
])
def test_r7_a_write_inside_the_repository_is_still_certain(commande):
    assert actes.ecrit(commande, RACINE_DEPOT) is True


def test_r7_without_a_root_nothing_is_filtered():
    assert actes.ecrit("pytest -q > /tmp/out.txt") is True


@pytest.mark.parametrize("commande,attendu", [
    ("pnpm run lint -- --fix", True), ("npm run lint -- --fix", True), ("pnpm lint --fix", True),
    ("pnpm run lint", False), ("pnpm run migrate:status", False), ("python manage.py migrate", False),
    ("python manage.py makemigrations", True),
])
def test_r7_lint_fix_rewrites_but_database_migrations_do_not_touch_tracked_files(commande, attendu):
    assert actes.ecrit(commande) is attendu


# --- relecture n° 8 (2026-10-26, FAIL): un geste git dans le dépôt VOISIN (Shinzo) n'est pas un geste d'ici ------
# La règle de conduite fait commiter Shinzo à chaque fin de séance. Le drapeau « état partagé » court-circuitait
# le test « dans le dépôt », et un chemin relatif qui sort par `..` comptait comme interne.

@pytest.mark.parametrize("commande", [
    "git -C ../Shinzo commit -m x", "cd ../Shinzo && git add -- 02-Projets/Kata.md && git commit -m x",
    "git -C D:/30-Dev-Projects/Shinzo commit -m x", "git -C ../Shinzo push", "git -C /d/30-Dev-Projects/Shinzo pull",
    "echo x >> ../Shinzo/02-Projets/Kata.md", "cd ../Shinzo && echo x >> 02-Projets/Kata.md",
    "echo x > D:/30-Dev-Projects/Kata-autre/x.txt", "echo x > /d/30-Dev-Projects/Kata-autre/x.txt",
    "echo x > D:/30-Dev-Projects/Kata/../Shinzo/x", 'echo x > "$HOME/a.txt"', 'echo x > "$TMPDIR/a.txt"',
    "git -C D:/30-Dev-Projects/Kata-autre commit -m x",
])
def test_r8_a_gesture_aimed_at_a_neighbouring_repository_is_not_one_of_this_repository(commande):
    assert actes.ecrit(commande, RACINE_DEPOT) is False
    assert actes.touche_etat_partage(commande, RACINE_DEPOT) is False


@pytest.mark.parametrize("commande", [
    "git commit -m x", "git -C . commit -m x", "git -C docs commit -m x", "cd docs && git commit -m x",
    "git -C D:/30-Dev-Projects/Kata commit -m x", "git -C docs/../src commit -m x", "echo x > docs/../a.md",
])
def test_r8_a_gesture_in_this_repository_is_still_one(commande):
    assert actes.ecrit(commande, RACINE_DEPOT) is True


@pytest.mark.parametrize("chemin,attendu", [
    (r"..\Shinzo\x", False), ("../Shinzo/x", False), ("docs/../a.md", True), ("D:/30-Dev-Projects/Kata", True),
    (r"D:\30-Dev-Projects\Kata\docs", True), ("d:/30-dev-projects/kata/x", True),
    ("D:/30-Dev-Projects/Kata-autre", False), ("/d/30-Dev-Projects/Kata-autre/x", False), ("", True),
])
def test_r8_the_repository_boundary_reads_like_a_path_not_like_a_prefix(chemin, attendu):
    assert actes.dans_le_depot(chemin, RACINE_DEPOT) is attendu
    assert actes.dans_le_depot(chemin, RACINE_DEPOT.replace("/", "\\")) is attendu
