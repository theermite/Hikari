#!/usr/bin/env python3
"""Simple Language check — Stop hook (WARN + state persistence for next-turn injection).

Enforces the 8 Simple Language constraints from rules/Honesty.md
on Takumi's most recent assistant response.

Scans the latest assistant text from the transcript (the response
Jay just read) and flags violations:

  1. Sentence > 25 words (constraint 5)
  2. Paragraph > 3 sentences (constraint 5)
  3. More than 1 acronym per paragraph (constraint 2)
  4. More than 1 acronym per sentence (constraint 6 — Jay 2026-05-31)
  5. Response > 3 prose paragraphs (constraint 8 — Jay 2026-06-07, short by default)

Code blocks (``` and `inline`) are stripped before analysis —
jargon inside code is allowed (variable names, error messages).
Tables, lists, blockquotes are NOT counted as prose paragraphs.

Output: WARNING on stderr if violations detected (Jay sees it).
        Plus persists to state file simple-language-violations-<session>.json
        so the UserPromptSubmit companion hook (simple-language-inject.py)
        can re-inject the violations into Takumi's NEXT context — Option A
        equivalent-of-BLOCKING for a Stop hook (Jay 2026-06-01).
        Exit 0 always (never blocks the response that was already emitted).

Status: Functional BLOCKING via Option A (next-turn injection). Promoted
        from pure WARN 2026-06-01 after recurring drift despite written rule.

Source: rules/Honesty.md "Simple Language — Anti-Jargon Rule"
        + Jay frustrations #2/#3/#4 (2026-05-31, cadre Expert
        Monozukuri / collaborateur non-technique).
        + Jay 2026-06-01 — WARN alone insufficient, need observable cost.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
LIB_DIR = HOOK_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from common import pass_through, read_hook_input  # noqa: E402
from session_state import write_state  # noqa: E402
from transcript_reader import iter_assistant_text  # noqa: E402


MAX_WORDS_PER_SENTENCE = 25
MAX_SENTENCES_PER_PARAGRAPH = 3
MAX_ACRONYMS_PER_PARAGRAPH = 1
MAX_ACRONYMS_PER_SENTENCE = 1
MAX_PROSE_PARAGRAPHS_PER_RESPONSE = 3

# Match fenced code blocks (```...```) and inline code (`...`)
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")

# Acronym = 2+ uppercase letters in a row (jargon proxy)
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}[A-Z0-9]*\b")

# Sentence splitter: ., !, ? followed by whitespace or EOL
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")

# Acronyms universal enough to skip flagging
_ACRONYM_ALLOWLIST = {
    "OK", "URL", "API", "CLI", "UI", "UX", "ID", "OS", "FAQ",
    "PDF", "HTML", "CSS", "JSON", "YAML", "TIME",
}

# Constraint 1 (BLUF) — staging openers that bury the conclusion.
# Matched at the very start of the response (markdown markers stripped).
_BLUF_FORBIDDEN_OPENERS = (
    "après analyse", "après vérification", "après une analyse",
    "après un examen", "après investigation", "après avoir",
    "suite à l'analyse", "suite à analyse", "suite à une analyse",
    "following",
)

# Constraint 10 — condescendance markers (Jay is HPI, never infantilize).
# Curated tight to avoid false positives ("la réponse est simple : oui").
_CONDESCENDANCE = (
    "pour faire simple", "pour simplifier", "en gros", "basiquement",
    "c'est très simple", "rien de compliqué", "ne t'inquiète pas",
    "pas besoin de comprendre", "comme tu le sais déjà",
)

# Constraint 6 extension — bare lowercase dev-jargon that should be
# translated or glossed in chat with Jay. Curated tight: unambiguous
# dev terms with a plain-French equivalent, that Jay would not use himself.
# Words Jay already knows (hook, commit, test, bug, script) are NOT here.
_JARGON_LOWER = {
    "payload", "endpoint", "middleware", "runtime", "boilerplate",
    "wrapper", "parsing", "deserialization", "idempotent", "nonce",
    "mutex", "throughput", "async",
}


def _strip_code(text: str) -> str:
    """Remove fenced and inline code blocks."""
    text = _CODE_BLOCK_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    return text


def _split_paragraphs(text: str) -> list[str]:
    """Split text into non-empty paragraphs (double newline)."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into non-empty sentences."""
    parts = _SENTENCE_SPLIT_RE.split(paragraph)
    return [s.strip() for s in parts if s.strip()]


def _count_words(sentence: str) -> int:
    """Count words by splitting on whitespace, ignoring markdown markers."""
    cleaned = re.sub(r"[*_#>|\-`]+", " ", sentence)
    return len([w for w in cleaned.split() if w])


def _count_acronyms(paragraph: str) -> int:
    """Count non-allowlisted acronyms in paragraph."""
    found = _ACRONYM_RE.findall(paragraph)
    return sum(1 for a in found if a not in _ACRONYM_ALLOWLIST)


def _is_structural(para: str) -> bool:
    """True if paragraph is mostly a table / list / blockquote (not prose)."""
    lines = para.split("\n")
    structural = sum(
        1 for line in lines
        if line.lstrip().startswith(("|", "-", "*", ">"))
        or re.match(r"^\s*\d+\.\s", line)
    )
    return structural >= max(1, len(lines) // 2)


def _check_bluf(text: str) -> list[str]:
    """Constraint 1 — flag a staging opener that buries the conclusion."""
    head = re.sub(r"^[*_#>\-\s]+", "", text).lower()[:80]
    for opener in _BLUF_FORBIDDEN_OPENERS:
        if head.startswith(opener):
            return [
                f"Conclusion noyee (BLUF, contrainte 1): la reponse ouvre par "
                f"\"{opener}...\" au lieu du resultat. Mettre la conclusion en 1re phrase."
            ]
    return []


def _check_condescendance(text: str) -> list[str]:
    """Constraint 10 — flag infantilizing markers (Jay is HPI, not a novice)."""
    low = text.lower()
    return [
        f"Marqueur de condescendance \"{p}\" (contrainte 10): Jay est HPI, "
        f"pas novice. Simplifier le vocabulaire, jamais le contenu."
        for p in _CONDESCENDANCE
        if p in low
    ]


def _jargon_in(sentence: str) -> list[str]:
    """Return bare lowercase dev-jargon tokens present in the sentence."""
    tokens = set(re.findall(r"[a-zA-Z]+", sentence.lower()))
    return sorted(tokens & _JARGON_LOWER)


def _check_sentence(sent: str, i: int, j: int) -> list[str]:
    """Per-sentence checks: word count, acronym density, bare jargon."""
    out: list[str] = []
    preview = sent[:60].replace("\n", " ")
    n_words = _count_words(sent)
    if n_words > MAX_WORDS_PER_SENTENCE:
        out.append(
            f"Paragraphe {i} phrase {j}: {n_words} mots "
            f"(max {MAX_WORDS_PER_SENTENCE}) - \"{preview}...\""
        )
    n_acronyms = _count_acronyms(sent)
    if n_acronyms > MAX_ACRONYMS_PER_SENTENCE:
        out.append(
            f"Paragraphe {i} phrase {j}: {n_acronyms} acronymes dans la meme "
            f"phrase (max {MAX_ACRONYMS_PER_SENTENCE} - Honesty.md contrainte 6) "
            f"- \"{preview}...\""
        )
    jargon = _jargon_in(sent)
    if jargon:
        out.append(
            f"Paragraphe {i} phrase {j}: jargon non glose {jargon} (contrainte 6) "
            f"- traduire en francais ou gloser entre parentheses."
        )
    return out


def _check_paragraph(para: str, i: int) -> list[str]:
    """Per-paragraph checks: sentence count, then each sentence, then acronyms."""
    out: list[str] = []
    sentences = _split_sentences(para)
    if len(sentences) > MAX_SENTENCES_PER_PARAGRAPH:
        out.append(
            f"Paragraphe {i}: {len(sentences)} phrases "
            f"(max {MAX_SENTENCES_PER_PARAGRAPH})"
        )
    for j, sent in enumerate(sentences, 1):
        out.extend(_check_sentence(sent, i, j))
    n_acronyms = _count_acronyms(para)
    if n_acronyms > MAX_ACRONYMS_PER_PARAGRAPH:
        out.append(
            f"Paragraphe {i}: {n_acronyms} acronymes non gloses "
            f"(max {MAX_ACRONYMS_PER_PARAGRAPH} - cf. Honesty.md contrainte 2)"
        )
    return out


def _analyze(text: str) -> list[str]:
    """Return list of human-readable Simple Language violations."""
    clean = _strip_code(text)
    violations: list[str] = []
    violations.extend(_check_bluf(clean))
    violations.extend(_check_condescendance(clean))

    prose_count = 0
    for i, para in enumerate(_split_paragraphs(clean), 1):
        if _is_structural(para):  # tables/lists are not prose
            continue
        prose_count += 1
        violations.extend(_check_paragraph(para, i))

    if prose_count > MAX_PROSE_PARAGRAPHS_PER_RESPONSE:
        violations.append(
            f"Reponse: {prose_count} paragraphes de prose "
            f"(max {MAX_PROSE_PARAGRAPHS_PER_RESPONSE} - Honesty.md "
            f"contrainte 8). Couper sauf si Jay a demande un audit / brief."
        )

    return violations


def _emit_warning(violations: list[str]) -> None:
    """WARN on stderr (Jay's console) — the response is already emitted."""
    sys.stderr.write(
        "[SIMPLE LANGUAGE WARN] Honesty.md contrainte violee dans la "
        "derniere reponse Takumi:\n"
    )
    for v in violations[:8]:
        sys.stderr.write(f"  - {v}\n")
    if len(violations) > 8:
        sys.stderr.write(f"  (+{len(violations) - 8} autres)\n")
    sys.stderr.write(
        "Reformuler au prochain tour: conclusion d'abord, phrases courtes, "
        "jargon glose, zero condescendance, tableau si comparaison.\n"
    )
    sys.stderr.flush()


def _persist(violations: list[str], session_id: str) -> None:
    """Persist for next-turn injection (Option A — Jay 2026-06-01).

    The companion UserPromptSubmit hook simple-language-inject.py reads this
    state and injects the violations into Takumi's next context, then clears
    `pending`. Equivalent-of-BLOCKING for a Stop hook (which cannot rewrite an
    already-emitted response). State write is best-effort — never break a session.
    """
    try:
        write_state(
            "simple-language-violations",
            {"pending": True, "violations": violations[:20]},
            session_id=session_id or None,
        )
    except Exception:
        pass


def _latest_response(transcript_path: str) -> str | None:
    """Return Takumi's most recent assistant text, or None if unavailable."""
    try:
        chunks = list(iter_assistant_text(transcript_path, limit=1))
    except Exception:
        return None
    return chunks[0] if chunks else None


def main() -> None:
    _, data = read_hook_input()
    transcript_path = data.get("transcript_path") or ""
    session_id = data.get("session_id") or ""
    if not transcript_path:
        pass_through()

    text = _latest_response(transcript_path)
    if text is None:
        pass_through()

    violations = _analyze(text)
    if violations:
        _emit_warning(violations)
        _persist(violations, session_id)

    pass_through()


if __name__ == "__main__":
    main()
