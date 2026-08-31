"""Tests for lib/secret_mask.py — the shared secret detector/masker.

Origin: docs/Briefs/Hook-Masquage-Secrets-Sorties-Bash-2026-08-30.md.
Two real incidents leaked production secrets into a conversation the same
evening (2026-08-30, Shinkofa-Backend session) because nothing inspected
command OUTPUT — only PreToolUse hooks inspect the command text itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import secret_mask as sm  # noqa: E402


# --- Incident A (brief §2) — ${VAR:+..}${VAR:-..} glues a value onto text ---


def test_incident_a_password_glued_after_prefix_is_masked():
    # brief §2 genericizes the real variable to "MA_VAR" for the write-up;
    # the real incident's name WAS a recognizable secret name (name family).
    raw = "POSTGRES_PASSWORD: presenteSuperSecretP4ss!!"
    masked = sm.mask_text(raw)
    assert "SuperSecretP4ss" not in masked
    assert "<masque:" in masked


def test_incident_a_unrecognized_var_name_is_the_honest_limit():
    # §6: a secret with no recognizable name AND no recognizable form
    # passes through. MA_VAR is neither a secret keyword nor base64/hex-shaped.
    raw = "MA_VAR: presenteabsente"
    assert sm.mask_text(raw) == raw


def test_incident_a_length_is_preserved_in_marker():
    value = "abcXYZ123!!"
    raw = f"POSTGRES_PASSWORD: {value}"
    masked = sm.mask_text(raw)
    assert f"<masque:{len(value)} car.>" in masked
    assert value not in masked


# --- Incident B (brief §2) — docker compose config resolves .env values ----


def test_incident_b_docker_compose_config_password_masked():
    raw = (
        "services:\n"
        "  db:\n"
        "    environment:\n"
        "      POSTGRES_PASSWORD: Tr0ub4dor&3xtraLongProdValue\n"
        "      POSTGRES_USER: shinkofa\n"
    )
    masked = sm.mask_text(raw)
    assert "Tr0ub4dor" not in masked
    assert "POSTGRES_USER: shinkofa" in masked  # non-secret name untouched


def test_incident_b_database_url_with_credentials_masked():
    raw = "DATABASE_URL: postgres://shinkofa_app:hunter2ProdPass@10.0.0.5:5432/prod"
    masked = sm.mask_text(raw)
    assert "hunter2ProdPass" not in masked
    assert "postgres://" not in masked  # whole credentialed URL is the secret


# --- Name family (brief §4) --------------------------------------------------


def test_token_name_masked():
    raw = "API_KEY=abcdefghijklmnopqrst1234"
    masked = sm.mask_text(raw)
    assert "abcdefghijklmnopqrst1234" not in masked


def test_webhook_secret_masked():
    raw = "STRIPE_WEBHOOK_SECRET: whsec_1234567890abcdefghijklmnop"
    masked = sm.mask_text(raw)
    assert "whsec_1234567890abcdefghijklmnop" not in masked


# --- Form family (brief §4) --------------------------------------------------


def test_pem_private_key_block_masked():
    raw = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEAxyz0123456789abcdefghijklmnopqrstuvwxyzABCDEFGH\n"
        "MIIEowIBAAKCAQEAxyz0123456789abcdefghijklmnopqrstuvwxyzABCDEFGH\n"
        "-----END RSA PRIVATE KEY-----\n"
    )
    masked = sm.mask_text(raw)
    assert "MIIEow" not in masked
    assert "<masque:" in masked


def test_bare_jwt_masked():
    raw = "Authorization returned: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    masked = sm.mask_text(raw)
    assert "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" not in masked


def test_isolated_base64_token_masked():
    raw = "session token: aGVsbG9Xb3JsZFRoaXNJc0FTZWNyZXRUb2tlbg=="
    masked = sm.mask_text(raw)
    assert "aGVsbG9Xb3JsZFRoaXNJc0FTZWNyZXRUb2tlbg==" not in masked


# --- False positives to avoid (brief §5) ------------------------------------


def test_backup_script_file_paths_not_masked():
    raw = (
        "/srv/backups/shinkofa-postgres-daily-2026-08-30-full-dump.sql.gz\n"
        "/var/www/theermite.com/releases/20260830-041502-abcdef012345/index.html\n"
    )
    masked = sm.mask_text(raw)
    assert masked == raw


def test_isolated_pem_header_without_body_not_masked():
    # write-guard's own incident C (brief §2): a doc that only NAMES the
    # PEM header, with no encoded body following, is not a real key.
    raw = "Detect a PEM block: lines starting with -----BEGIN RSA PRIVATE KEY-----."
    masked = sm.mask_text(raw)
    assert masked == raw


def test_plain_prose_untouched():
    raw = "Le deploiement a reussi en 4.2s, 12 fichiers modifies."
    assert sm.mask_text(raw) == raw


def test_short_token_below_threshold_not_masked():
    raw = "id: a1b2c3d4e5f6"  # 12 chars, under the 32-char form floor
    assert sm.mask_text(raw) == raw


# --- Independent review 2026-08-31: over-masking erased the variable NAME ---


def test_generic_key_suffix_is_recognized():
    # cross-model-sonnet, 4th review: MASTER_KEY, ENCRYPTION_KEY,
    # SESSION_KEY, JWT_SIGNING_KEY are common production secret names, but
    # "KEY" was only accepted inside 3 hard-coded compounds (API/PRIVATE/
    # ACCESS-KEY) — never as a generic "*_KEY" suffix. Reproduced: both
    # layers (mask + alert net share has_secret) stayed silent.
    for name in ("MASTER_KEY", "ENCRYPTION_KEY", "SESSION_KEY", "JWT_SIGNING_KEY"):
        assert sm.has_secret(f"{name}=8f3a1c2e9b7d4f60"), name


def test_monkey_and_keyboard_are_not_falsely_flagged():
    # the generic "*_KEY" suffix requires an explicit "_"/"-" separator
    # right before KEY, so words that merely CONTAIN "key" as a substring
    # (no separator) do not turn every identifier into a false alarm.
    assert sm.mask_text("MONKEY_PATCH=enabled") == "MONKEY_PATCH=enabled"
    assert sm.mask_text("KEYBOARD_LAYOUT=azerty") == "KEYBOARD_LAYOUT=azerty"


def test_authorization_header_is_recognized():
    # cross-model-sonnet, 8th review: round 7's letter-boundary fix for bare
    # "AUTH" (closing AUTHOR/SecretString) accidentally reopened the most
    # common real-world realization of AUTH — the HTTP `Authorization`
    # header (`curl -v`, gateway/nginx logs). AUTHORIZATION and
    # AUTHENTICATE have a letter right after AUTH, same shape as AUTHOR,
    # so they got silently excluded too.
    assert sm.has_secret("Authorization: Bearer tok_9f8e7d6c5b4a")
    assert sm.has_secret("Authorization: Basic YWRtaW46U3VwM3JTZWNyZXQh")
    assert sm.has_secret("WWW-Authenticate: Bearer error=invalid_token")
    # AUTHOR itself must stay excluded (round 7's original fix, not undone)
    assert not sm.has_secret("Author: The Ermite <example@example.com>")


def test_multi_param_auth_scheme_fully_masked():
    # cross-model-sonnet, 10th review (2nd FAIL on the SAME family as round
    # 9): round 9's fix counted exactly 2 words (scheme + one credential),
    # which breaks on any HTTP auth scheme whose credential is a
    # multi-parameter list (MAC, Digest, AWS SigV4) — words 3+ leaked in
    # clear. Per Independent-Review.md, a 2nd failure on the same family
    # means changing approach, not patching a 3rd hardcoded word: capture
    # to end-of-line (unquoted) or to the matching quote (JSON), not a word
    # count.
    mac = 'Authorization: MAC id="h480djs93hd8", ts="1336363200", nonce="dj83hs9s", mac="bhCQXTVyfj5cmA9uKkPFx1zAtB7"'
    masked = sm.mask_text(mac)
    assert "bhCQXTVyfj5cmA9uKkPFx1zAtB7" not in masked
    assert "h480djs93hd8" not in masked


def test_auth_header_still_bounded_to_its_own_line():
    # the end-of-line capture must not swallow the NEXT header when curl -v
    # prints several, one per line.
    block = "Authorization: Bearer tok_9f8e7d6c5b4a\nAccept: */*"
    masked = sm.mask_text(block)
    assert "tok_9f8e7d6c5b4a" not in masked
    assert "Accept: */*" in masked


def test_authorization_header_credential_is_actually_removed():
    # cross-model-sonnet, 9th review: round 8's own tests only asserted
    # has_secret() (a boolean: "did SOMETHING change") — true the moment
    # the scheme word ("Bearer"/"Basic") got masked, even though the real
    # credential right after it was never touched. Tautological test, real
    # leak: assert on the CREDENTIAL's absence, the same pattern already
    # used correctly for the JWT case above.
    tok = "tok_9f8e7d6c5b4a"
    masked = sm.mask_text(f"Authorization: Bearer {tok}")
    assert tok not in masked

    b64 = "YWRtaW46U3VwM3JTZWNyZXQh"
    masked = sm.mask_text("Authorization: Basic " + b64)
    assert b64 not in masked

    oauth = "ya29." + "a0AfH6SMBx7dQK9pL3vN8xR2tY5wU1cJ4hG6fB9mZ3nQ8pL2vX7sT4wY9cR1"
    masked = sm.mask_text(f"Authorization: Bearer {oauth}")
    assert oauth not in masked

    masked = sm.mask_text(f"Proxy-Authorization: Bearer {tok}")
    assert tok not in masked


def test_bare_keyword_substring_false_positives_fixed():
    # cross-model-sonnet, 7th review: AUTH/SECRET/TOKEN matched as a FREE
    # SUBSTRING with no separator requirement (unlike KEY, fixed in round
    # 4) — so AUTHOR, SecretString (round 6's own false hit, treated then
    # as a one-off), TOKENIZER_CONFIG, SECRETARIAT_ID all got masked as if
    # they were secrets. Worst case: `git log`'s own "Author: Name" line
    # triggered the alert net on every single git command of the session.
    assert sm.mask_text("AUTHOR: John Smith") == "AUTHOR: John Smith"
    assert sm.mask_text("Author: The Ermite <example@example.com>") == "Author: The Ermite <example@example.com>"
    assert sm.mask_text("TOKENIZER_CONFIG=default") == "TOKENIZER_CONFIG=default"
    assert sm.mask_text("SECRETARIAT_ID: 42") == "SECRETARIAT_ID: 42"
    assert not sm.has_secret("Author: The Ermite <example@example.com>")


def test_bare_keyword_still_recognized_as_standalone_or_compound():
    # the fix must not re-close what rounds 1-6 already opened: bare
    # keyword alone, and compounds joined by `_`/`-`, still work.
    assert sm.has_secret("SECRET=abcdefghijklmnop")
    assert sm.has_secret("AUTH_TOKEN=abcdefghijklmnop")
    assert sm.has_secret("CLIENT_SECRET=abcdefghijklmnop")
    assert sm.has_secret("STRIPE_WEBHOOK_SECRET=abcdefghijklmnop")


def test_json_quoted_key_is_recognized():
    # cross-model-sonnet, 6th review: `aws secretsmanager get-secret-value`
    # and `vault kv get` (both explicitly targeted by pre-bash-secret-mask)
    # emit JSON by default, where the name is quoted ("password":"value")
    # — the closing quote sat between the name and the separator, breaking
    # the match entirely, for every name/separator/case already covered.
    raw = '{"data":{"password":"hunter2ProdPassword"},"metadata":{}}'
    masked = sm.mask_text(raw)
    assert "hunter2ProdPassword" not in masked
    assert '"password"' in masked


def test_vault_kv_get_json_realistic_output_masked():
    # the realistic, common form of `vault kv get -format=json` /
    # `aws secretsmanager get-secret-value` (name/value both quoted, single
    # level of JSON) is masked by the fix above.
    raw = '{"data":{"data":{"password":"hunter2ProdPassword"},"metadata":{}}}'
    masked = sm.mask_text(raw)
    assert "hunter2ProdPassword" not in masked


def test_doubly_escaped_json_string_is_the_honest_limit():
    # AWS Secrets Manager's raw `SecretString` field is itself a
    # JSON-serialized string, so the name/value pair is escaped a SECOND
    # time (`\"password\":\"...\"` — backslash-quote, not a plain quote).
    # Un-escaping arbitrary nesting depth is a JSON-parsing problem, not a
    # name/value regex one; chasing it invites unbounded escaping levels
    # (double, triple...). Documented limit, not silently pretended fixed.
    raw = '{"SecretString": "{\\"username\\":\\"admin\\",\\"password\\":\\"Cor4ectHorseBattery\\"}"}'
    masked = sm.mask_text(raw)
    assert "Cor4ectHorseBattery" in masked  # honest limit: not masked


def test_quoted_multiword_value_fully_masked():
    # cross-model-sonnet, 3rd review: an unquoted value stops at the first
    # space, masking only "correct" out of a multi-word passphrase. A
    # quoted value has an unambiguous end, so it CAN be masked in full.
    raw = 'DB_PASSWORD: "correct horse battery staple"'
    masked = sm.mask_text(raw)
    assert "correct" not in masked
    assert "horse" not in masked
    assert "battery" not in masked
    assert "staple" not in masked


def test_unquoted_multiword_value_is_the_honest_limit():
    # Without a delimiter, masking past the first word would swallow
    # unrelated text after it (the exact over-masking family closed in the
    # 1st review) — this stays a documented limit, not a silent claim.
    raw = "DB_PASSWORD: correct horse battery staple"
    masked = sm.mask_text(raw)
    assert "correct" not in masked  # first word still masked
    assert "horse battery staple" in masked  # rest is the honest limit


def test_hyphenated_api_key_name_is_recognized():
    # cross-model-sonnet, 2nd review 2026-08-31: "api-key", "access-key",
    # "private-key" (AWS/Terraform/k8s convention) escaped detection because
    # only an underscore was accepted between the compound-name parts.
    assert sm.has_secret("api-key: shortsecret1234567890")
    assert sm.has_secret("access-key: shortsecret1234567890")
    assert sm.has_secret("private-key: shortsecret1234567890")


def test_form_mask_never_swallows_an_unrecognized_variable_name():
    # MAJOR found by cross-model-sonnet: `=` inside the isolated-token
    # charset let a whole `NAME=value` pair (name included) match as one
    # "isolated token" whenever the name itself did not match the secret
    # keyword list — erasing information the brief explicitly requires kept
    # ("la longueur reste visible... la variable est-elle definie ?").
    raw = "GIT_COMMIT_SHA=8f14e45fceea167a5a36dedd4bea2543"
    masked = sm.mask_text(raw)
    assert masked.startswith("GIT_COMMIT_SHA=")
    assert "8f14e45fceea167a5a36dedd4bea2543" not in masked


# --- has_secret() — used by the PostToolUse alert net -----------------------


def test_has_secret_true_on_named_secret():
    assert sm.has_secret("DB_PASSWORD=hunter2ProdValueLongEnough") is True


def test_has_secret_false_on_clean_output():
    assert sm.has_secret("All tests passed: 42/42") is False


# --- Independent review 2026-08-31 round 5, famille complexite-quadratique --


def test_mask_text_stays_fast_on_many_isolated_tokens():
    # cross-model-sonnet, 5th review, proven by real execution: _form_spans
    # compared each new match against EVERY match already accepted (O(n) per
    # match => O(n^2) overall). A realistic `docker inspect`/`kubectl get
    # secret` output can carry thousands of digest-shaped tokens — exactly
    # what this hook is wrapped around. Measured before the fix: 8000 tokens
    # took 3.4s, growing much faster than linearly; this bounds it well
    # under that regime.
    import secrets
    import string
    import time

    def token(n=40):
        return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n))

    text = " ".join(token() for _ in range(8000))
    start = time.time()
    sm.mask_text(text)
    elapsed = time.time() - start
    assert elapsed < 2.0, f"mask_text took {elapsed:.2f}s on 8000 tokens (quadratic regression?)"
