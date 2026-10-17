#!/usr/bin/env python3
"""Fail if any .env.example contains something that looks like a real secret."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK_MARKERS = ("change-me", "example", "placeholder", "localhost", "127.0.0.1")
SENSITIVE_KEY = re.compile(r"(SECRET|PASSWORD|TOKEN|KEY|COMMUNITY|URL)", re.IGNORECASE)
EMBEDDED_CREDS = re.compile(r"://[^/\s:@]+:([^@\s]+)@")

bad: list[str] = []
for f in ROOT.rglob(".env.example"):
    for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        if SENSITIVE_KEY.search(key) and not any(m in val.lower() for m in OK_MARKERS):
            bad.append(f"{f.relative_to(ROOT)}:{n} (sensitive key)")
        m = EMBEDDED_CREDS.search(val)
        if m and not any(ok in m.group(1).lower() for ok in OK_MARKERS):
            bad.append(f"{f.relative_to(ROOT)}:{n} (embedded credential)")

if bad:
    print("Possible real secret in example env:")
    for b in bad:
        print(f"  {b}")
    sys.exit(1)
print("check_secrets_placeholders: OK")
