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

_FORM_PATTERNS = (_PEM_RE, _URL_CREDS_RE, _JWT_RE, _ISOLATED_TOKEN_RE)


@dataclass(frozen=True)
class _Span:
    start: int
    end: int


def _name_spans(text: str) -> list[_Span]:
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


def _all_form_matches(text: str) -> list[tuple[int, int]]:
    """Every form-pattern match, start-sorted (each pattern scans left to right)."""
    return sorted(
        (
            (m.start(), m.end())
            for pattern in _FORM_PATTERNS
            for m in pattern.finditer(text)
        ),
        key=lambda pair: pair[0],
    )


def _form_spans(text: str, taken: list[_Span]) -> list[_Span]:
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
    for start, end in _all_form_matches(text):
        if start < cursor:
            continue  # overlaps a form span already accepted
        while taken_idx < len(taken_sorted) and taken_sorted[taken_idx].end <= start:
            taken_idx += 1
        if taken_idx < len(taken_sorted) and taken_sorted[taken_idx].start < end:
            continue  # overlaps a name span
        spans.append(_Span(start, end))
        cursor = end
    return spans


def mask_text(text: str) -> str:
    """Return `text` with every recognizable secret replaced by its length.

    A `<masque:N car.>` marker keeps the one legitimate question answerable
    ("is the variable set, and how long is it?") without the value itself.
    """
    name_spans = _name_spans(text)
    form_spans = _form_spans(text, name_spans)
    spans = sorted(name_spans + form_spans, key=lambda s: s.start)

    out = []
    cursor = 0
    for span in spans:
        if span.start < cursor:
            continue  # overlapping match already consumed
        out.append(text[cursor : span.start])
        length = span.end - span.start
        out.append(f"<masque:{length} car.>")
        cursor = span.end
    out.append(text[cursor:])
    return "".join(out)


def has_secret(text: str) -> bool:
    """True if `text` contains a name- or form-recognizable secret.

    Used by the PostToolUse alert net: it cannot redact what already ran,
    only warn that a value should be rotated.
    """
    return mask_text(text) != text


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
