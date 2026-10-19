"""Second independent review 2026-10-19 on 3876526 (FAIL, famille: texte-neutralise-mais-execute).

The first fix erased a substitution's fixed text before judging the command. Fixed text is inert
only while it stays a MESSAGE: handed to `sh -c`, `eval`, `python -c`, `xargs` or a variable that is
then run, it executes — and the guard no longer saw it. The regex also ended a heredoc at the
first `EOF)` where bash ends it at the first line equal to `EOF`. Approach changed: text is exempt
only as the direct value of a git/gh message option, and a heredoc ends where bash ends it.
Second defect: with the light mask on file tools, a Phoenix `prod.secret.exs` came back in clear.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]
REDACT = HOOKS / "guards" / "post-tool-secret-redact.py"
READ_GUARD = HOOKS / "guards" / "secret-file-read-guard.py"


def _guard(command: str) -> int:
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
    return subprocess.run([sys.executable, str(READ_GUARD)], input=json.dumps(payload).encode(),
                          capture_output=True, timeout=10).returncode


def test_fixed_text_handed_to_something_that_runs_it_is_refused():
    for cmd in (
        "git commit -m \"$(cat <<'EOF'\nmsg\nEOF\ncat .env\nEOF\n)\"",
        "git commit -m \"$(cat <<EOF\nmsg\nEOF\ncat .env\nEOF\n)\"",
        "echo \"$(cat <<\"EOF\"\nmsg\nEOF\nbase64 .env\nEOF\n)\"",
        "git commit -m \"$(cat <<-'EOF'\n\tmsg\n\tEOF\ncat .env\nEOF\n)\"",
        "sh -c \"$(cat <<'EOF'\ncat .env\nEOF\n)\"",
        "eval \"$(cat <<'EOF'\ncat .env\nEOF\n)\"",
        "c=\"$(cat <<'EOF'\ncat .env\nEOF\n)\"; $c",
        "bash -c \"$(printf 'cat .env')\"",
        "eval \"$(echo 'cat .env')\"",
        "python3 -c \"$(cat <<'EOF'\nprint(open('.env').read())\nEOF\n)\"",
        "echo \"$(echo '.env')\" | xargs cat",
        "bash <<'EOF'\ncat .env\nEOF",
        "cat <<'EOF' | bash\ncat .env\nEOF",
    ):
        assert _guard(cmd) == 2, cmd


def test_forged_message_owners_are_refused():
    # 3rd review on 62878ba: a fake `git commit -m` inside `bash -c "..."` hid a read. Without any
    # message exemption (Jay 2026-10-19) the raw text names the file and the command is refused.
    # The `eval "...git commit -m ..."` variant predates 2026-10-19: text run by a shell, a known limit.
    for cmd in (
        "bash -c \"true;git commit -m \"$(cat <<'EOF'\nx;cat<.env\nEOF\n)\"\"",
        "git commit -m \"$(cat <<'EOF'\ncat .env\nEOF\n)\"",
    ):
        assert _guard(cmd) == 2, cmd


def test_ordinary_messages_stay_accepted():
    # 4th review on 84ba1e8: the refusal promises `-F -`; that form must carry any message text,
    # backticks, `$(...)` and a line starting with `eval` included.
    for cmd in (
        "git commit -q -F - <<'EOF'\nfix: .env et server.key cités, sans substitution\nEOF",
        "git commit -F - <<'EOF'\nfix(hooks): `cat .env` est refusé\nEOF",
        "git commit -F - <<'EOF'\nfix(hooks): refuse -m \"$(cat .env)\"\nEOF",
        "git commit -F - <<'EOF'\ndocs: `docker compose --env-file .env` charge les variables\neval reste refusé avec .env\nEOF",
        "gh pr create --title \"fix(hooks): y\" --body \"$(cat <<'EOF'\n- notes (a & b)\nEOF\n)\"",
        "git commit -m \"a; b\" -m \"$(cat <<'EOF'\nfix(x): corps\nEOF\n)\"",
        "git -C ../app commit -m \"$(cat <<'EOF'\nchore: deps\nEOF\n)\" && git push",
        "docker compose --env-file .env up -d --build && echo \"built $(date)\" && bash scripts/smoke.sh",
    ):
        assert _guard(cmd) == 0, cmd


def test_the_refusal_names_the_commit_form_that_works():
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": "git commit -m \"$(cat <<'EOF'\nchore: .env\nEOF\n)\""}}
    r = subprocess.run([sys.executable, str(READ_GUARD)], input=json.dumps(payload).encode(),
                       capture_output=True, timeout=10)
    assert r.returncode == 2 and "git commit -F -" in r.stderr.decode("utf-8")


def _redact(tool: str, response):
    payload = {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_response": response}
    r = subprocess.run([sys.executable, str(REDACT)], input=json.dumps(payload).encode(),
                       capture_output=True, timeout=10)
    out = r.stdout.decode("utf-8").strip()
    return json.loads(out)["hookSpecificOutput"]["updatedToolOutput"] if out else response


def test_phoenix_and_dotnet_secret_files_are_secret_files():
    sys.path.insert(0, str(HOOKS / "lib"))
    from secret_files import is_secret_file
    for p in ("config/prod.secret.exs", "app/appsettings.Production.json", "/home/u/.config/rclone/rclone.conf",
              "deploy/env.production"):
        assert is_secret_file(p), p
    for p in ("priv/repo/migrations/env.py", "alembic/env.py", "src/env.ts", "config/prod.exs"):
        assert not is_secret_file(p), p


def test_read_of_a_phoenix_secret_file_is_masked():
    content = 'config :app, App.Repo, password: "Pr0d-db-pass", url: "ecto://u:Pr0d-db-pass@db.prod/app"\n'
    out = _redact("Read", {"type": "text", "file": {"filePath": "/repo/config/prod.secret.exs", "content": content}})
    assert "Pr0d-db-pass" not in json.dumps(out)


def test_grep_lines_from_a_secret_file_are_masked_and_code_lines_are_not():
    code = 'test/auth_test.exs:12:    register_user(%{email: "a", password: "not valid"})'
    content = f"/repo/.env:3:DB_PASSWORD=Pr0d-db-pass\n{code}\n"
    out = _redact("Grep", {"mode": "content", "content": content, "numLines": 2})
    text = json.dumps(out)
    assert "Pr0d-db-pass" not in text and 'password: \\"not valid\\"' in text
