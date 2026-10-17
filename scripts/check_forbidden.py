#!/usr/bin/env python3
"""Repo guard: fail if a forbidden term appears anywhere in tracked content.

The term is assembled at runtime so this file does not itself contain it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TERMS = ["kav" + "ach"]
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "__pycache__", ".mypy_cache",
    ".ruff_cache", ".pytest_cache", "dist", "SBOM",
}
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
    ".tar", ".gz", ".whl", ".so", ".dylib", ".dll", ".exe", ".bin",
    ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".mp4", ".mov",
    ".db", ".sqlite", ".sqlite3",
}


def main() -> int:
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(p in SKIP_DIRS for p in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() in BINARY_EXT:
            continue
        rel = path.relative_to(ROOT)
        haystack = [str(rel).lower()]
        try:
            haystack.append(path.read_text(encoding="utf-8", errors="ignore").lower())
        except OSError:
            continue
        if any(t in h for t in TERMS for h in haystack):
            hits.append(str(rel))
    if hits:
        print("FORBIDDEN TERM FOUND IN:")
        for h in hits:
            print(f"  {h}")
        return 1
    print("check_forbidden: OK (0 matches)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
