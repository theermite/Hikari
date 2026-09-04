#!/usr/bin/env python3
"""Open the private update channel on the VPS. Runs ON the VPS, as the `ubuntu` user.

    python3 setup_update_channel.py <private-path-segment>

The segment is an argument, never a literal in this file: this repository is public.

WHY THIS SCRIPT VERIFIES ITS OWN EFFECT INSTEAD OF TRUSTING ITS EDIT
--------------------------------------------------------------------
The first version of this step used `sed` to insert the block. An independent review
found the defect that matters here: when the anchor pattern does not match, `sed` changes
nothing, exits 0, and the caller happily runs `nginx -t` on the UNCHANGED file, reloads,
and prints "channel open". A success message on work that never happened — and the failure
only surfaces later, as an update that silently never arrives.

The family is not "a fragile regex". It is "a step that reports success without checking
what it actually achieved". So every stage below asserts the achieved state:

  1. the target `server` block is identified by its OWN content (`listen 443` +
     `server_name`), never by position in the file;
  2. after writing, the file is re-read and the block must be present INSIDE that block —
     if not, the backup is restored and the script fails loudly;
  3. `nginx -t` gates the reload, and a failure restores the backup;
  4. finally, the channel is probed over real HTTPS. That last check is the only one that
     proves the thing Jay cares about: a file placed here is reachable from his machine.

`deck.shinkofa.com` also serves a live streaming deck. Nothing is reloaded until nginx
itself says the file parses, and any failure puts the original back.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

SITE = Path("/etc/nginx/sites-available/deck.shinkofa.com")
ENABLED = Path("/etc/nginx/sites-enabled/deck.shinkofa.com")
# A plain POSIX string, never a `Path`: `Path` renders with the HOST separator, so a
# dry-run of this logic on Windows produced `alias \home\ubuntu\...` in the nginx
# block. The config text must never depend on the machine that composed it.
TARGET_DIR = "/home/ubuntu/apps/hikari-updates"
SERVER_NAME = "deck.shinkofa.com"
PROBE_NAME = "channel-probe.txt"
PROBE_BODY = "hikari-update-channel-ok"


def sudo(*command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sudo", *command], capture_output=True, text=True)


def find_tls_server_block(config: str) -> tuple[int, int]:
    """Span of the `server { ... }` block that actually serves HTTPS for this host.

    Identified by content, never by position: a Certbot-shaped file carries a second
    `server` block on port 80 whose only job is a redirect, and inserting there would
    produce a channel that parses, reloads, and is never reachable over HTTPS.
    """
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\bserver\s*\{", config):
        start = match.end() - 1
        depth = 0
        for index in range(start, len(config)):
            if config[index] == "{":
                depth += 1
            elif config[index] == "}":
                depth -= 1
                if depth == 0:
                    spans.append((match.start(), index + 1))
                    break

    matching = [
        (start, end)
        for start, end in spans
        if "listen 443" in config[start:end] and SERVER_NAME in config[start:end]
    ]
    if len(matching) != 1:
        raise SystemExit(
            f"expected exactly one TLS server block for {SERVER_NAME}, found {len(matching)}"
        )
    return matching[0]


def location_block(segment: str) -> str:
    return (
        f"\n    # Canal prive de mise a jour Hikari (application desktop) : manifeste\n"
        f"    # signe + installeur. Hors de Hikari-Deck/dist, qu'une reconstruction\n"
        f"    # du deck efface.\n"
        f"    location /{segment}/ {{\n"
        f"        alias {TARGET_DIR}/;\n"
        f"        autoindex off;\n"
        f'        add_header Cache-Control "no-store" always;\n'
        f"    }}\n"
    )


def insert_block(config: str, segment: str) -> str:
    """Put the location block at the END of the TLS server block, just before its `}`.

    Placement inside the block is what matters, not the order among siblings: nginx picks
    a prefix location by longest match, never by the order it was written.
    """
    start, end = find_tls_server_block(config)
    closing = config.rfind("}", start, end)
    return config[:closing] + location_block(segment) + config[closing:]


def assert_block_is_live(segment: str) -> None:
    """Re-read the file from disk and require the block INSIDE the TLS server block."""
    config = SITE.read_text(encoding="utf-8")
    start, end = find_tls_server_block(config)
    if f"location /{segment}/" not in config[start:end]:
        raise SystemExit(
            "the location block is NOT in the TLS server block after writing — "
            "the edit did not take effect"
        )


def probe(segment: str, attempts: int = 6, delay: float = 1.0) -> None:
    """Fetch a known file through the real public URL, retrying briefly.

    The only check that proves the channel works from OUTSIDE; everything above only
    proves the file parses. It retries because `systemctl reload` returns as soon as the
    signal is sent, not once the new workers serve traffic: a single immediate request is
    answered by a worker still running the OLD config, and comes back as the deck's
    index.html. Measured here on 2026-09-04 — the first run failed for exactly that reason
    while the channel was in fact correct."""
    (Path(TARGET_DIR) / PROBE_NAME).write_text(PROBE_BODY, encoding="utf-8")
    url = f"https://{SERVER_NAME}/{segment}/{PROBE_NAME}"
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=15) as response:  # noqa: S310 - fixed https host
                last = response.read().decode("utf-8", "replace").strip()
        except OSError as error:
            last = f"<{error}>"
        if last == PROBE_BODY:
            print(f"probe OK: {url} (attempt {attempt})")
            return
        time.sleep(delay)
    raise SystemExit(
        f"probe returned {last[:120]!r} instead of {PROBE_BODY!r} — channel not serving"
    )


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1]:
        raise SystemExit("usage: setup_update_channel.py <private-path-segment>")
    segment = sys.argv[1]

    if ENABLED.resolve() != SITE:
        raise SystemExit(f"{ENABLED} does not resolve to {SITE} — refusing to edit a file nginx may not read")

    Path(TARGET_DIR).mkdir(parents=True, exist_ok=True)

    config = SITE.read_text(encoding="utf-8")
    if f"location /{segment}/" in config:
        print("channel already configured — verifying it serves")
        probe(segment)
        return 0
    if "hikari-updates" in config:
        raise SystemExit(
            "a hikari-updates location already exists under a DIFFERENT segment — "
            "remove it by hand before opening a new one"
        )

    # `with_suffix` would eat the `.com` of the domain name and produce
    # `deck.shinkofa.bak-...`. The backup must stay obviously paired with its file.
    backup = SITE.with_name(f"{SITE.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    sudo("cp", str(SITE), str(backup))
    print(f"backup: {backup}")

    updated = insert_block(config, segment)
    staged = Path("/tmp/deck.shinkofa.com.staged")
    staged.write_text(updated, encoding="utf-8")
    sudo("cp", str(staged), str(SITE))

    try:
        assert_block_is_live(segment)
        test = sudo("nginx", "-t")
        if test.returncode != 0:
            raise SystemExit(f"nginx -t failed:\n{test.stderr}")
        reload = sudo("systemctl", "reload", "nginx")
        if reload.returncode != 0:
            raise SystemExit(f"nginx reload failed:\n{reload.stderr}")
    except SystemExit:
        sudo("cp", str(backup), str(SITE))
        sudo("systemctl", "reload", "nginx")
        print("FAILED — original config restored and reloaded", file=sys.stderr)
        raise

    print("channel open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
