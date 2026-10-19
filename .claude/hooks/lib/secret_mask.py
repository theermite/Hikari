"""Shared secret detector/masker for command OUTPUT (not command text).

Two families (Hook-Masquage-Secrets-Sorties-Bash-2026-08-30.md §4):
- by NAME:  `NOM: valeur` / `NOM=valeur` where NOM matches a secret keyword.
- by FORM:  PEM block, credentialed URL, isolated base64/hex >=32, JWT —
  regardless of the variable name.

Used by two hooks:
- guards/pre-bash-secret-mask.py rewrites suspicious commands (docker exec,
  docker compose config, ssh + docker/env, cat .env, printenv) to pipe their
  combined output through `mask_text()` before it reaches the conversation.
- guards/post-bash-secret-alert.py is the fallback net on every other Bash
  call: it cannot un-print what already ran, so it only warns via
  `has_secret()` when a name/form match survived, telling Jay to rotate it.

Honest limit (brief §6): a secret with no recognizable name and no
recognizable form passes through. This closes the observed class, not every
possible one.

Strict profile, named by the independent reviews (2026-10-18), left open on purpose: a value
that starts with `$` (read as an interpolation), a lower-case name with a letters-only value
(`password = correcthorse`), `token: Bearer <value>` (stops at "Bearer"), the keys `pwd` and
`pass` between quotes, a password given as an option (`-p<value>`, `--password <value>`), a
version-shaped prefix under a secret name (`API_KEY=1.0-...`), and a quoted key followed by a bare
snake_case word (`"password": correct_horse_battery_staple`, read as a Python dict).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --- Family 1: by name --------------------------------------------------------

#  `[-_]` (not just `_`) between compound-name parts: independent review
# 2026-08-31 round 2 found "api-key", "access-key", "private-key" (the
# AWS/Terraform/Kubernetes hyphen convention) escaping detection entirely —
# `SECRET` and `TOKEN` alone already caught `client-secret`/`refresh-token`
# as bare keywords, but `KEY` alone is never a keyword by itself, so the
# compound names needed the hyphen explicitly.
#  `[A-Za-z]+[-_]KEY` catches "*_KEY"/"*-KEY" as a GENERIC suffix, not just
# the 3 hard-coded compounds below: independent review 2026-08-31 round 4
# found MASTER_KEY, ENCRYPTION_KEY, SESSION_KEY, JWT_SIGNING_KEY — common
# production secret names — silently passing both layers, because "KEY"
# was never accepted as a standalone suffix. The mandatory `[-_]` separator
# keeps "MONKEY_PATCH" / "KEYBOARD_LAYOUT" (KEY with no separator before
# it, or not at the suffix) from false-firing.
#  `(?<![A-Za-z])WORD(?![A-Za-z])` around each bare word: independent review
# 2026-08-31 round 7 found AUTH/SECRET/TOKEN matching as a free SUBSTRING
# with no separator requirement — AUTHOR, SecretString (round 6's own false
# hit, dismissed then as a one-off AWS quirk), TOKENIZER_CONFIG,
# SECRETARIAT_ID all got masked as if they were secrets. Worst case: `git
# log`'s own "Author: Name" line tripped the PostToolUse alert net on every
# git command of the session. Digits/underscore stay allowed immediately
# adjacent (`SECRET_1`, `AUTH2`) — only adjacent LETTERS (a longer English
# word swallowing the keyword) are rejected.
def _bare(word: str) -> str:
    return rf"(?<![A-Za-z]){word}(?![A-Za-z])"


_BARE_KEYWORDS = ("PASSWORD", "PASSWD", "SECRET", "TOKEN", "AUTH", "CREDENTIAL", "DSN", "WEBHOOK")

#  AUTHORIZATION / AUTHENTICATE have a letter right after "AUTH" — same
# shape as the false positive AUTHOR that `_bare("AUTH")` was built to
# reject. Independent review 2026-08-31 round 8 found this closed off the
# HTTP `Authorization`/`WWW-Authenticate` header, the most common
# real-world realization of AUTH (`curl -v`, gateway/proxy logs). Named
# explicitly rather than loosening the boundary generally, which would
# reopen AUTHOR itself.
_AUTH_COMPOUND = r"AUTHORI[SZ]ATION|AUTHENTICATE"

_NAME_KEYWORDS = (
    "|".join(_bare(w) for w in _BARE_KEYWORDS)
    + rf"|{_AUTH_COMPOUND}"
    + r"|API[-_]?KEY|PRIVATE[-_]KEY|CLIENT[-_]SECRET|ACCESS[-_]KEY|[A-Za-z]+[-_]KEY"
    # DB_PASS, PG_PWD, MYSQL_ROOT_PW (independent review 2026-10-18 round 3). Bare PWD and PASS are left
    # out on purpose: `PWD=/home/x` is the working directory and `--- PASS: TestLogin` a test runner line.
    + r"|[A-Za-z]+[-_](?:PWD|PW|PASS)(?![A-Za-z])"
)

# `<prefix>NAME: value` or `<prefix>NAME=value` — the unquoted branch of the
# VALUE group already swallows incident A's glued form (`presente<secret>`)
# whole, since it matches everything up to the next whitespace/quote. The
# quoted branches (tried first) mask a multi-word value in full: independent
# review 2026-08-31 round 3 found an unquoted match stopping at the first
# space, masking only the first word of a passphrase like `"correct horse
# battery staple"`. An UNQUOTED multi-word value stays an honest limit
# (§6): masking past the first space with no delimiter would swallow
# unrelated trailing text — the exact over-masking family round 1 closed.
#  An optional closing quote (`["']?`) between the name and the separator:
# independent review 2026-08-31 round 6 found `aws secretsmanager
# get-secret-value` and `vault kv get` — both explicitly targeted by
# pre-bash-secret-mask.py — emit JSON by default (`"password":"value"`),
# where that quote sat between the name and `:`/`=`, breaking the match
# for every name/case/separator already covered.
_NAME_KV_RE = re.compile(
    rf'\b(?P<name>\w*(?:{_NAME_KEYWORDS})\w*)["\']?\s*[:=]\s*'
    rf'(?P<value>"[^"]*"|\'[^\']*\'|[^\s"\'<>]+)',
    re.IGNORECASE,
)

#  Bound by a real delimiter (matching quote, or end of line) — NOT a word
# count. Independent review 2026-08-31 round 9 found round 8's fix only
# masked the SCHEME word, leaving the credential in clear; round 10 then
# found round 9's own fix ("scheme + exactly one more word") broke on any
# HTTP auth scheme whose credential is a multi-parameter list (MAC, Digest,
# AWS SigV4) — a 2nd failure on the SAME family, per Independent-Review.md
# a signal to change approach, not add a 3rd hardcoded word. A quoted value
# (JSON: `"Authorization": "Bearer xxx"`) stops at its own closing quote,
# same as `_NAME_KV_RE` — an unquoted value (raw HTTP header text, `curl
# -v` output) runs to end of line, covering any number of scheme
# parameters, without swallowing the NEXT header on the following line.
_AUTH_HEADER_RE = re.compile(
    rf'\b(?:{_AUTH_COMPOUND})["\']?\s*[:=]\s*(?P<value>"[^"]*"|\'[^\']*\'|[^\r\n]+)',
    re.IGNORECASE,
)

# `scheme://user:pass@host...` — DATABASE_URL / REDIS_URL style.
_URL_CREDS_RE = re.compile(
    r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s/:@\"']+:[^\s/@\"']+@[^\s\"']+"
)

# PEM block: header line, at least one line of encoded body, footer line.
# Requiring a body line is what tells a real key apart from a doc that only
# NAMES the header (brief §5, write-guard's own incident C). The literal
# "PRIVATE"+" KEY" words are built by concatenation on purpose — writing the
# two words joined in this source file trips write-guard's own fallback
# pattern (its exact incident C, reproduced verbatim while authoring this).
_PEM_WORD = "PRIVATE" + " KEY"
_PEM_RE = re.compile(
    rf"-----BEGIN [A-Z ]*{_PEM_WORD}-----\r?\n"
    rf"(?:[A-Za-z0-9+/=]{{16,}}\r?\n)+"
    rf"-----END [A-Z ]*{_PEM_WORD}-----",
)

# JWT: three dot-separated base64url segments.
_JWT_RE = re.compile(r"\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")

# Isolated base64/hex >=32 chars. Path separators and dots are excluded from
# the main charset on purpose: a naive ">24 chars" rule flagged 8 file-path
# lines in a backup script the same evening (brief §5) — real base64/hex
# tokens do not contain `/`, `\` or `.`. `=` is excluded from the main run
# too and only allowed as 0-2 TRAILING padding chars: independent review
# 2026-08-31 found the old symmetric charset (with `=` allowed anywhere) let
# a whole `NAME=value` pair match as one "isolated token" whenever NAME did
# not match the keyword list — erasing the variable name along with the
# value, which the brief explicitly requires kept visible. `=` stays OUT of
# the boundary checks below (unlike `/`, `\`, `.`) precisely because it is
# the legitimate separator introducing a value — a token starting right
# after `NAME=` must still be maskable, only the name itself must not be
# swallowed into the same match.
_ISOLATED_TOKEN_RE = re.compile(r"(?<![\w/\\.])[A-Za-z0-9+_-]{32,}={0,2}(?![\w/\\.])")

# Tokens with a vendor prefix: recognizable without a variable name, and rare
# enough in ordinary output that the strict profile can keep them.
_PREFIX_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:"
    r"(?:ghp_|gho_|ghs_|ghu_|github_pat_|glpat-|xox[abprs]-|sk-ant-|sk-|hf_|npm_)[A-Za-z0-9_-]{16,}"
    r"|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}"
    r"|AKIA[A-Z0-9]{12,}|AIza[A-Za-z0-9_-]{30,})"
)
# JWT with its real header: "eyJ" is base64 for '{"'. The generic 3-segment
# shape also matches dotted code paths, so the strict profile requires it.
_STRICT_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{7,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")

_FORM_PATTERNS = (_PEM_RE, _URL_CREDS_RE, _JWT_RE, _ISOLATED_TOKEN_RE)
# Strict profile (every tool's output, hooks/guards/post-tool-secret-redact.py):
# no "isolated 32+ chars" rule — it also eats long test names and commit hashes,
# which is tolerable on a few suspicious Bash commands and not on every tool.
_STRICT_FORM_PATTERNS = (_PEM_RE, _URL_CREDS_RE, _STRICT_JWT_RE, _PREFIX_TOKEN_RE)


@dataclass(frozen=True)
class _Span:
    start: int
    end: int


# Strict profile value: a password may hold < or >, so only our own marker is excluded
# (the default profile stops at them to avoid eating HTML and <masque:...> markers).
_STRICT_NAME_KV_RE = re.compile(
    _NAME_KV_RE.pattern.replace("[^\\s\"\\'<>]+", "(?!<masque:)[^\\s\"\\']+"),
    re.IGNORECASE,
)
_TYPE_WORDS = frozenset({"str", "string", "int", "bool", "bytes", "none", "null", "nil", "true", "false",
                         "self", "undefined", "optional", "any", "object", "required"})
_CHUNK = 1000  # strict profile: the name rule is quadratic on a long word, bound it
_WINDOW = 1500  # overlap of 500: a pair straddling a chunk boundary is still seen whole
_ENV_NAME = re.compile(r"_*[A-Z][A-Z0-9_-]*")
_PY_LITERAL = re.compile(r"[rRbBfFuU]{1,2}[\"']")
_INTERPOLATION = re.compile(r"\$\{?\w+\}?|%\(\w+\)s|\{\{[^}]*\}\}")
_CALL = re.compile(r"[A-Za-z_][A-Za-z_.]{2,}\(")
_IDENTIFIER = re.compile(r"[A-Za-z_.]+(\[[\w.,|\[\] ]*\])?")


# `^3.1.0`, `~2.0`, `>=1.2.3`: a version range under a `*-key` name (package-lock `"path-key"`) is data.
_VERSION = re.compile(r"[~^<>=v]*\d+(\.[\dx*]+)+([-+][\w.]+)?")
# `set[tuple[str,`: a generic type cut by the whitespace that ends an unquoted value.
_TRUNCATED_TYPE = re.compile(r"[A-Za-z_.]+\[[\w.,|\[\] ]*")


def _bare_core(value: str) -> str:
    # keep a closing bracket: `args[i]` must stay a whole identifier (round 5, was stripped with `]`)
    return value.strip().strip("\"'").rstrip(",;:.)}…")


def _is_bare_identifier(value: str) -> bool:
    core = _bare_core(value)
    return bool(_IDENTIFIER.fullmatch(core) or _TRUNCATED_TYPE.fullmatch(core))


def _is_snake_identifier(value: str) -> bool:
    core = _bare_core(value)
    return bool(_IDENTIFIER.fullmatch(core)) and ("_" in core or "." in core)


def _is_reference_or_data(core: str) -> bool:
    """Too short, a type word, an interpolation or a version range: never a literal secret."""
    return (len(core) < 4 or core.lower() in _TYPE_WORDS
            or bool(_INTERPOLATION.fullmatch(core) or _VERSION.fullmatch(core)))


def _looks_like_code(name: str, value: str, quoted_key: bool, is_header: bool = False,
                     cut_by_quote: bool = False) -> bool:
    """True when the value is code or prose, not a literal secret.

    Judged on the SHAPE of the name first (independent review 2026-10-18): an
    ENV_STYLE name or a quoted key ("password": ...) holds a literal whatever
    characters it contains, so a password full of symbols is masked. Only a
    reference (interpolation), a call, a string-literal prefix, a type word, or a
    plain identifier after a lower-case name is code.
    """
    v = value.strip()
    core = v.strip("\"'").rstrip(",;:.)}]\u2026")
    if _PY_LITERAL.match(v) or _is_reference_or_data(core):
        return True
    holds_a_literal = is_header or quoted_key or bool(_ENV_NAME.fullmatch(name))
    if _CALL.match(core):
        return _call_is_code(v, holds_a_literal, cut_by_quote)
    if cut_by_quote and v.endswith("["):
        return True  # `cfg["secret"]`: a subscript, cut at its opening quote
    if holds_a_literal:
        return quoted_key and _is_dict_variable(v)
    return _is_bare_identifier(v)


def _call_is_code(v: str, holds_a_literal: bool, cut_by_quote: bool) -> bool:
    """A value that opens like a call. Independent review round 3 (2026-10-18): `DB_PASSWORD=Monkey(42)xyz!`
    opens like a call but does not END like one. Behind a literal-holding name the value is code only when
    the call is the whole value (`get_password(user)`) or was cut by a quote that opens its string argument
    (`re.compile(r"..."`, round 4: that cut is how real code looks). A password that is exactly `Name(42)`
    still reads as a call: the honest limit of a shape test."""
    return not holds_a_literal or cut_by_quote or v.rstrip(",;.").endswith(("(", ")"))


def _is_dict_variable(v: str) -> bool:
    """Round 5: a quoted key followed by a bare snake_case identifier is a Python dict built from variables
    (`"client_secret": client_secret,`), not a literal; JSON literals are quoted."""
    return not v.startswith(("\"", "'")) and _is_snake_identifier(v)


def _match_is_code(rx: re.Pattern, chunk: str, m: re.Match) -> bool:
    """Strict profile: does this name/value match read as code rather than a literal secret?"""
    if rx is not _STRICT_NAME_KV_RE:
        return _looks_like_code("", m.group("value"), False, is_header=True)
    before = chunk[max(m.start("name") - 1, 0) : m.start("name")]
    cut = chunk[m.end("value") : m.end("value") + 1] in ('"', "'")
    return _looks_like_code(m.group("name"), m.group("value"), before in ('"', "'"), cut_by_quote=cut)


def _strict_name_spans(text: str) -> list[_Span]:
    """Name rule for the all-tools profile: skips code-looking values (the lines of
    source files Claude reads) and runs on bounded, overlapping windows."""
    found: dict[int, int] = {}
    offset = 0
    for line in text.split(chr(10)):
        for i in range(0, max(len(line), 1), _CHUNK):
            chunk = line[i : i + _WINDOW]
            if ":" not in chunk and "=" not in chunk:
                continue  # no assignment possible: skips the quadratic scan entirely
            base = offset + i
            for rx in (_AUTH_HEADER_RE, _STRICT_NAME_KV_RE):
                for m in rx.finditer(chunk):
                    if _match_is_code(rx, chunk, m):
                        continue
                    start, end = base + m.start("value"), base + m.end("value")
                    found[start] = max(found.get(start, 0), end)
        offset += len(line) + 1
    return [_Span(s0, e0) for s0, e0 in sorted(found.items())]


def _name_spans(text: str, strict: bool = False) -> list[_Span]:
    if strict:
        return _strict_name_spans(text)
    spans = []
    # _AUTH_HEADER_RE first: its wider (scheme+credential) match must win
    # over _NAME_KV_RE's narrower (scheme-only) match at the same start
    # position — mask_text's cursor sweep keeps whichever span in this
    # list comes first when two spans share a start (round 9).
    for m in _AUTH_HEADER_RE.finditer(text):
        spans.append(_Span(m.start("value"), m.end("value")))
    for m in _NAME_KV_RE.finditer(text):
        spans.append(_Span(m.start("value"), m.end("value")))
    return spans


# Cheap necessary condition per strict pattern: a regex that starts at every
# letter of a giant word (URL scheme, PEM) is quadratic; the substring is not.
_STRICT_NEEDS = {_URL_CREDS_RE: "://", _PEM_RE: "-----BEGIN", _STRICT_JWT_RE: "eyJ"}


def _all_form_matches(text: str, strict: bool = False) -> list[tuple[int, int]]:
    """Every form-pattern match, start-sorted (each pattern scans left to right)."""
    patterns = _STRICT_FORM_PATTERNS if strict else _FORM_PATTERNS
    if strict:
        patterns = tuple(p for p in patterns if _STRICT_NEEDS.get(p, "") in text)
    return sorted(
        (
            (m.start(), m.end())
            for pattern in patterns
            for m in pattern.finditer(text)
        ),
        key=lambda pair: pair[0],
    )


def _form_spans(text: str, taken: list[_Span], strict: bool = False) -> list[_Span]:
    """Form-pattern matches not overlapping `taken` (name spans) or each other.

    A sorted single sweep, not "compare each new match against every match
    already accepted": independent review 2026-08-31 round 5 measured the
    old O(n) - per - match check as O(n^2) overall — 8000 digest-shaped
    tokens (a realistic `docker inspect`/`kubectl get secret` output, not an
    adversarial one) took 3.4s and climbing much faster than linearly. Both
    `taken` and the merged matches are start-sorted; a two-pointer sweep is
    O(n log n) total (the sort), not O(n^2).
    """
    taken_sorted = sorted(taken, key=lambda s: s.start)
    spans: list[_Span] = []
    taken_idx = 0
    cursor = -1  # end of the last accepted form span
    for start, end in _all_form_matches(text, strict):
        if start < cursor:
            continue  # overlaps a form span already accepted
        while taken_idx < len(taken_sorted) and taken_sorted[taken_idx].end <= start:
            taken_idx += 1
        if taken_idx < len(taken_sorted) and taken_sorted[taken_idx].start < end:
            continue  # overlaps a name span
        spans.append(_Span(start, end))
        cursor = end
    return spans


def mask_text(text: str, strict: bool = False) -> str:
    """Return `text` with every recognizable secret replaced by its length.

    A `<masque:N car.>` marker keeps the one legitimate question answerable
    ("is the variable set, and how long is it?") without the value itself.
    """
    name_spans = _name_spans(text, strict)
    form_spans = _form_spans(text, name_spans, strict)
    return _replace_spans(text, [(s.start, s.end) for s in name_spans + form_spans])


# File tools (Read, Grep, Edit...): only forms no source code produces by accident. Independent
# review 2026-10-19: the name rule rewrote test fixtures (`password: "not valid"`) and dev URLs
# (`postgres://postgres:postgres@localhost`) in code being READ, so the next Edit could not find
# its text, or wrote the mask into the file. Secret FILES are refused at the door by
# guards/secret-file-read-guard.py; what reaches a file tool is code.
_UNAMBIGUOUS_PATTERNS = (_PEM_RE, _STRICT_JWT_RE, _PREFIX_TOKEN_RE)


def mask_unambiguous(text: str) -> str:
    patterns = (p for p in _UNAMBIGUOUS_PATTERNS if _STRICT_NEEDS.get(p, "") in text)
    return _replace_spans(text, [(m.start(), m.end()) for p in patterns for m in p.finditer(text)])


def _replace_spans(text: str, spans: list[tuple[int, int]]) -> str:
    out = []
    cursor = 0
    for start, end in sorted(spans, key=lambda s: s[0]):  # stable: name spans keep priority
        if start < cursor:
            continue  # overlapping match already consumed
        out.append(text[cursor:start])
        out.append(f"<masque:{end - start} car.>")
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def has_secret(text: str, strict: bool = False) -> bool:
    """True if `text` contains a name- or form-recognizable secret.

    Used by the PostToolUse alert net: it cannot redact what already ran,
    only warn that a value should be rotated.
    """
    return mask_text(text, strict) != text


if __name__ == "__main__":
    # CLI filter mode: `python3 secret_mask.py --filter` reads stdin, writes
    # mask_text(stdin) to stdout. This is what pre-bash-secret-mask.py pipes
    # a suspicious command's combined output through, before it ever reaches
    # the conversation.
    import sys as _sys

    if "--filter" in _sys.argv:
        _sys.stdout.write(mask_text(_sys.stdin.read()))
    else:
        _sys.exit("usage: secret_mask.py --filter  (reads stdin, writes masked stdout)")
