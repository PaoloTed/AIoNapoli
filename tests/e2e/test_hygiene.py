"""Repository hygiene tests ensuring no secrets or personal absolute paths are committed."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ("backend", "shared", "database", "tests", "pyproject.toml", "assumptions.md")
TEXT_SUFFIXES = {
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".sql",
    ".md",
    ".toml",
    ".csv",
    ".xml",
    ".txt",
}


def test_nessun_segreto() -> None:
    """NFR-07: repository contains no secrets, private keys, or personal absolute paths."""
    secret_patterns = [
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"ghp_[A-Za-z0-9]{20,}"),
        re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
    ]
    personal_path_patterns = [
        re.compile("/" + "home/[A-Za-z0-9._-]+"),
        re.compile("/" + "Users/[A-Za-z0-9._-]+"),
        re.compile("[A-Za-z]:" + r"\\" + "Users" + r"\\" + "[A-Za-z0-9._-]+"),
    ]

    candidate_files: list[Path] = []
    for rel in SCAN_ROOTS:
        target = REPO_ROOT / rel
        if not target.exists():
            continue
        if target.is_file():
            candidate_files.append(target)
        else:
            for path in target.rglob("*"):
                if not path.is_file():
                    continue
                if any(
                    part in {"__pycache__", ".pytest_cache", ".venv", ".git"} for part in path.parts
                ):
                    continue
                if path.suffix.lower() in TEXT_SUFFIXES:
                    candidate_files.append(path)

    assert candidate_files
    for path in sorted(candidate_files):
        content = path.read_text(encoding="utf-8", errors="replace")
        for pat in (*secret_patterns, *personal_path_patterns):
            match = pat.search(content)
            assert match is None, (
                f"Disallowed pattern '{pat.pattern}' found in {path.relative_to(REPO_ROOT)}: "
                f"{match.group(0)!r}"
            )

    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore
