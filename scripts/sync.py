#!/usr/bin/env python3
"""Sync new chat.md entries to the AI team meeting room (pickles room).

Usage:
  ROOM_KEY=<key> python3 scripts/sync.py [--dry-run]

- Parses chat.md entries: header `### <sender> · <YYYY-MM-DD HH:MM>`, body until next header.
- Posts unsynced entries (hash not in synced.json) to the meeting room via curl.
- Records posted hashes in synced.json so nothing is posted twice.
- With --dry-run, prints what would be posted without posting or writing synced.json.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

CHAT = "chat.md"
SYNCED = "synced.json"
ROOM_URL = "https://ai-team-room.oouuu2.workers.dev/api/rooms/pickles/messages"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

HEADER_RE = re.compile(r"^###\s+(.+?)\s+·\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*$")


def parse(text):
    entries = []
    cur = None
    for line in text.splitlines():
        m = HEADER_RE.match(line)
        if m:
            if cur:
                entries.append(cur)
            cur = {"sender": m.group(1).strip(), "time": m.group(2).strip(), "body": []}
        elif cur is not None:
            cur["body"].append(line)
    if cur:
        entries.append(cur)
    out = []
    for e in entries:
        body = "\n".join(e["body"]).strip()
        if not body:
            continue
        h = hashlib.sha256(f"{e['sender']}|{e['time']}|{body}".encode("utf-8")).hexdigest()
        out.append({"sender": e["sender"], "time": e["time"], "body": body, "hash": h})
    return out


def post(sender, body):
    key = os.environ.get("ROOM_KEY", "")
    if not key:
        print("ROOM_KEY is not set; skipping post", file=sys.stderr)
        return False
    payload = json.dumps({"sender": sender, "content": body}, ensure_ascii=False)
    cmd = [
        "curl", "-sS", "--fail", "-A", UA, "-X", "POST",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer " + key,
        "--data", payload, ROOM_URL,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        print(f"posted {sender}: {r.stdout[:200]}")
        return True
    print(f"FAILED to post {sender}: {r.stderr.strip()[:300]}", file=sys.stderr)
    return False


def main():
    dry = "--dry-run" in sys.argv
    with open(CHAT, encoding="utf-8") as f:
        entries = parse(f.read())
    try:
        with open(SYNCED, encoding="utf-8") as f:
            synced = set(json.load(f))
    except Exception:
        synced = set()
    new = [e for e in entries if e["hash"] not in synced]
    print(f"total={len(entries)} new={len(new)} dry_run={dry}")
    for e in new:
        print(f"--- {e['sender']} · {e['time']}")
        print(e["body"])
        if dry:
            continue
        if post(e["sender"], e["body"]):
            synced.add(e["hash"])
        else:
            print(f"FAILED {e['hash']}", file=sys.stderr)
    if not dry:
        with open(SYNCED, "w", encoding="utf-8") as f:
            json.dump(sorted(synced), f, ensure_ascii=False, indent=2)
            f.write("\n")


if __name__ == "__main__":
    main()
