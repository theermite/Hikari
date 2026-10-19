"""Which paths ARE a secret file — the file's whole content is a secret (.env, key files, tokens).

Split out of guards/secret-file-read-guard.py on 2026-10-19 (the guard reached the 500-line
ceiling while fixing the independent review of that day). One concept: a path, a yes or no.
"""

from __future__ import annotations

import posixpath
import re

_TEMPLATE_SUFFIX = (".example", ".sample", ".template", ".dist", ".sops", ".age", ".enc",
                    ".gpg", ".vault", ".pub", ".d.ts", ".ts", ".md", ".schema.json", ".js", ".mjs", ".cjs")
_PUBLIC_CERTS = frozenset({"fullchain.pem", "cacert.pem", "chain.pem", "cert.pem",
                           "ca-bundle.pem", "ca-certificates.pem"})
_NAME_PATTERNS = (
    re.compile(r"^\.env($|[._-].+|rc$)"),
    re.compile(r"^.+\.(pem|key|p12|pfx)$"),
    re.compile(r"^id_(rsa|ed25519|ecdsa|dsa)"),
    re.compile(r"^.+\.env$"),
    re.compile(r"^(\.git-credentials|\.pypirc|\.htpasswd|credentials\.json|kubeconfig)$"),
    re.compile(r"^.+\.(ppk|tfvars)$"),
    re.compile(r"^(\.netrc|\.npmrc|\.pgpass|age-key\.txt|tokens\.env|\.secrets|\.vault-token|\.dockercfg|\.claude\.json)$"),
    re.compile(r"^.+\.tokens\.env$"),
    re.compile(r"^(secrets?\.(json|toml|ya?ml)|service[-_]account.*\.json|terraform\.tfstate(\.backup)?)$"),
    # independent review 2026-10-19: Phoenix runtime secrets, .NET per-environment settings, rclone
    # remotes, `env.production`-style files. `env.py` (Alembic) and `env.ts` stay code.
    re.compile(r"^(.+\.secret\.exs|appsettings\..+\.json|rclone\.conf)$"),
    re.compile(r"^env\.(prod|production|staging|stage|preprod|local|dev|development|test)$"),
    # 5th review 2026-10-19: Google OAuth client secrets, Django and WordPress settings that hold keys.
    re.compile(r"^(client_secret.*\.json|local_settings\.py|settings_local\.py|wp-config\.php)$"),
)
_PATH_PATTERNS = (
    re.compile(r"(^|/)\.aws/credentials$"),
    re.compile(r"(^|/)sops/age/keys\.txt$"),
    re.compile(r"(^|/)shinkofa-vault/envs(/|$)"),
    re.compile(r"(^|/)\.docker/config\.json$"),
    re.compile(r"(^|/)\.kube/config$"),
    re.compile(r"(^|/)\.claude/\.credentials\.json$"),
    re.compile(r"(^|/)gh/hosts\.yml$"),
    re.compile(r"(^|/)\.codex/auth\.json$"),
    re.compile(r"(^|/)gcloud/application_default_credentials\.json$"),
)
# `.bak`, `.old2`, and dated copies such as `rclone.conf.backup-2026-05-21` (5th review 2026-10-19:
# that real file on the server was not recognised and came back in clear).
_BACKUP_SUFFIX = re.compile(r"[._-](bak|old|orig|save|swp|tmp|backup)([._-][\w.-]*|\d*)$")
_ADS = re.compile(r"::.*$")  # NTFS alternate data stream: `.env::$DATA` is the same file


def _normal_name(norm: str) -> str:
    """The file name as the OS opens it: no stream, no trailing dot/space/tilde, no backup suffix."""
    name = _ADS.sub("", norm.rsplit("/", 1)[-1]).rstrip(" .~")
    return _BACKUP_SUFFIX.sub("", name)


def is_secret_file(path: str) -> bool:
    norm = _ADS.sub("", posixpath.normpath(path.replace("\\", "/")).lower())
    name = _normal_name(norm)
    if name.endswith(_TEMPLATE_SUFFIX) or name in _PUBLIC_CERTS:
        return False
    if any(p.search(norm) for p in _PATH_PATTERNS):
        return True
    return any(p.match(name) for p in _NAME_PATTERNS)


def glob_names_a_secret(glob: str) -> bool:
    """A Grep glob like `.env*` or `*.pem` aims at secret files."""
    alternatives = [glob]
    brace = re.search(r"\{([^{}]*)\}", glob)
    if brace:
        alternatives = [glob[: brace.start()] + opt + glob[brace.end():] for opt in brace.group(1).split(",")]
    probes = [p for alt in alternatives for p in (alt, alt.replace("*", "x"), alt.replace("*", ""))]
    return any(is_secret_file(p) for p in probes if p)
