#!/usr/bin/env python3
"""Register the Phase 3a-1 models in backend/app/models/__init__.py (idempotent, safe to re-run).

Why a script: that file is shared with Phases 1-2, and this phase must not overwrite your version of it.
The script adds ONE import line (in isort order, so ruff stays green) and the names to ``__all__``.
If it cannot understand the file it changes nothing and prints the two lines to add by hand.
"""

import re
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "backend" / "app" / "models" / "__init__.py"
NAMES = ("DeviceMetric", "DevicePollState", "InterfaceMetric", "SnmpCredentialProfile")
IMPORT = "from app.models.monitoring import DeviceMetric, DevicePollState, InterfaceMetric, SnmpCredentialProfile"
MANUAL = (f"Add this line with the other 'from app.models...' imports:\n  {IMPORT}\n"
          "and add these names to __all__: " + ", ".join(f'"{n}"' for n in NAMES))


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found. Run this from the repository root.")
        return 1
    text = TARGET.read_text(encoding="utf-8")
    if "app.models.monitoring" in text:
        print("models already registered: nothing to do")
        return 0
    lines = text.split("\n")
    imports = [(i, m.group(1)) for i, ln in enumerate(lines) if (m := re.match(r"from app\.models\.(\w+) import ", ln))]
    if not imports:
        print("ERROR: could not find 'from app.models.<x> import' lines.\n" + MANUAL)
        return 1
    # isort order: put the new line before the first module that sorts after "monitoring", else after the last.
    after = next((i for i, mod in imports if mod > "monitoring"), None)
    insert_at = after if after is not None else imports[-1][0] + 1
    lines.insert(insert_at, IMPORT)
    joined = "\n".join(lines)
    m = re.search(r"__all__\s*=\s*\[(.*?)\]", joined, re.S)
    if m is None:
        print("ERROR: could not find __all__ = [...].\n" + MANUAL)
        return 1
    body = m.group(1).rstrip()
    sep = "" if body.endswith(",") or not body.strip() else ","
    addition = "".join(f'\n    "{n}",' for n in NAMES)
    joined = joined[:m.start(1)] + body + sep + addition + "\n" + joined[m.end(1):]
    TARGET.write_text(joined, encoding="utf-8")
    print("registered Phase 3a-1 models in app/models/__init__.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
