"""AST-based architecture boundary enforcement tests (ARCHITECTURE.md §3)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"
STDLIB_MODULES = set(sys.stdlib_module_names)


def _iter_py_files(subdir: Path) -> list[Path]:
    return sorted(p for p in subdir.rglob("*.py") if "__pycache__" not in p.parts)


def _extract_imports(py_file: Path) -> list[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def test_core_senza_dipendenze() -> None:
    """NFR-02: domain/ must only import stdlib, pydantic, and app.domain."""
    for py_file in _iter_py_files(BACKEND_APP / "domain"):
        for mod in _extract_imports(py_file):
            top = mod.split(".")[0]
            allowed = (
                mod.startswith("app.domain")
                or top == "pydantic"
                or top in STDLIB_MODULES
                or mod == "__future__"
            )
            assert allowed, f"{py_file} imports disallowed module '{mod}'"


def test_agenti_isolati() -> None:
    """REQ-AGT-07: no agent package imports from another agent package."""
    agents_dir = BACKEND_APP / "services" / "agents"
    agent_names = ("mobility", "crowding", "context")
    for agent in agent_names:
        others = [a for a in agent_names if a != agent]
        for py_file in _iter_py_files(agents_dir / agent):
            for mod in _extract_imports(py_file):
                for other in others:
                    assert f"agents.{other}" not in mod, (
                        f"Agent '{agent}' in {py_file} imports '{mod}'"
                    )


def test_agenti_solo_repository() -> None:
    """REQ-AGT-08: agents read only from repositories, no direct HTTP except mobility -> OTP."""
    agents_dir = BACKEND_APP / "services" / "agents"
    http_libs = {"httpx", "requests", "urllib3", "aiohttp"}
    for py_file in _iter_py_files(agents_dir):
        is_otp_client = py_file.name == "otp_client.py" and py_file.parent.name == "mobility"
        for mod in _extract_imports(py_file):
            top = mod.split(".")[0]
            if not is_otp_client:
                assert top not in http_libs, f"{py_file} imports HTTP library '{mod}'"
            assert not mod.startswith("app.api"), f"{py_file} imports api '{mod}'"
            assert not mod.startswith("app.db"), f"{py_file} imports db '{mod}'"


def test_api_senza_dominio() -> None:
    """REQ-API-07: api/ endpoints never import repositories, db, drivers, or domain.logic."""
    api_dir = BACKEND_APP / "api"
    for py_file in _iter_py_files(api_dir):
        for mod in _extract_imports(py_file):
            assert not mod.startswith("app.repositories"), f"{py_file} imports repositories '{mod}'"
            assert not mod.startswith("app.db"), f"{py_file} imports db '{mod}'"
            assert not mod.startswith("app.domain"), f"{py_file} imports domain '{mod}'"
            assert mod.split(".")[0] not in {"psycopg", "sqlite3"}, (
                f"{py_file} imports DB driver '{mod}'"
            )


def test_driver_isolati() -> None:
    """REQ-PER-04: database drivers imported only in db/ and repositories/."""
    driver_mods = {"sqlite3", "psycopg", "psycopg_pool"}
    for py_file in _iter_py_files(BACKEND_APP):
        rel = py_file.relative_to(BACKEND_APP)
        in_allowed_dir = rel.parts[0] in ("db", "repositories")
        if in_allowed_dir:
            continue
        for mod in _extract_imports(py_file):
            assert mod.split(".")[0] not in driver_mods, (
                f"{py_file} imports DB driver '{mod}' outside db/ or repositories/"
            )


def test_connettori_senza_finding() -> None:
    """REQ-CONN-03: connectors never import Finding or domain finding models."""
    connectors_dir = BACKEND_APP / "services" / "connectors"
    for py_file in _iter_py_files(connectors_dir):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "finding" not in node.module.lower(), (
                    f"{py_file} imports finding module '{node.module}'"
                )
                for alias in node.names:
                    assert alias.name != "Finding", f"{py_file} imports Finding"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "finding" not in alias.name.lower(), (
                        f"{py_file} imports finding module '{alias.name}'"
                    )


def test_connettori_senza_soglie() -> None:
    """REQ-CONN-08: connectors never import orchestrator rules, thresholds, or priorities."""
    connectors_dir = BACKEND_APP / "services" / "connectors"
    for py_file in _iter_py_files(connectors_dir):
        for mod in _extract_imports(py_file):
            assert "orchestrator" not in mod, f"{py_file} imports orchestrator '{mod}'"
            assert not mod.startswith("app.domain.logic.rules"), f"{py_file} imports rules '{mod}'"
            assert not mod.startswith("app.domain.logic.priorities"), (
                f"{py_file} imports priorities '{mod}'"
            )
