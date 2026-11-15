#!/usr/bin/env python3
"""Verify that PostgreSQL, the OTP build directory and the live graph agree.

The check is read-only. It compares:

- ``public.gtfs_datasets.source_sha256`` with ``current.json`` and
  ``last-result.json``;
- the ZIPs copied into the active build directory;
- ``graph.obj`` with the SHA-256 recorded in ``current.json``;
- the ``otp-live`` symlink with the active build;
- the number of routes exposed by the live OTP graph with the database.

Exit code 0 means aligned; 1 means divergence or an unreadable state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import urllib.request
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE = REPO_ROOT / "data" / "otp-rebuild" / "current.json"
DEFAULT_RESULT = REPO_ROOT / "data" / "otp-rebuild" / "last-result.json"
DEFAULT_LIVE_LINK = Path("/home/r0x4n/otp-live")
DEFAULT_CONTAINER = "napoli-postgres-mobility"
DEFAULT_DATABASE = "mobility"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"file non leggibile: {path}: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"JSON non valido: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON non oggetto: {path}")
    return value


def compare_datasets(
    database: Mapping[str, Mapping[str, Any]],
    recorded: Mapping[str, Mapping[str, Any]],
    *,
    label: str,
) -> list[str]:
    """Return human-readable differences between DB and recorded dataset maps."""
    errors: list[str] = []
    db_keys = set(database)
    recorded_keys = set(recorded)
    if db_keys != recorded_keys:
        errors.append(
            f"{label}: dataset diversi: db={sorted(db_keys)} record={sorted(recorded_keys)}"
        )
    for key in sorted(db_keys & recorded_keys):
        db_sha = str(database[key].get("source_sha256") or "")
        recorded_sha = str(recorded[key].get("source_sha256") or "")
        if not db_sha or db_sha != recorded_sha:
            errors.append(
                f"{label}: hash diverso per '{key}': db={db_sha or 'assente'} "
                f"record={recorded_sha or 'assente'}"
            )
        db_schema = str(database[key].get("gtfs_schema") or "")
        recorded_schema = str(recorded[key].get("gtfs_schema") or "")
        if db_schema and recorded_schema and db_schema != recorded_schema:
            errors.append(
                f"{label}: schema diverso per '{key}': db={db_schema} "
                f"record={recorded_schema}"
            )
    return errors


def verify_build_artifacts(
    version: Path,
    database: Mapping[str, Mapping[str, Any]],
    *,
    graph_sha256: str | None,
) -> list[str]:
    """Verify the GTFS ZIPs and graph.obj inside an OTP build directory."""
    errors: list[str] = []
    otp_data = version / "otp-data"
    if not otp_data.is_dir():
        return [f"build: directory otp-data assente in {version}"]
    for key, row in sorted(database.items()):
        expected = str(row.get("source_sha256") or "")
        zip_path = otp_data / f"{key}.gtfs.zip"
        if not zip_path.is_file():
            errors.append(f"build: ZIP assente per '{key}': {zip_path}")
            continue
        actual = sha256_file(zip_path)
        if actual != expected:
            errors.append(
                f"build: hash ZIP diverso per '{key}': file={actual} db={expected}"
            )
    graph_path = otp_data / "graph.obj"
    if not graph_path.is_file():
        errors.append(f"build: graph.obj assente in {otp_data}")
    elif graph_sha256:
        actual = sha256_file(graph_path)
        if actual != graph_sha256:
            errors.append(
                f"build: graph.obj diverso da current.json: "
                f"file={actual} current={graph_sha256}"
            )
    return errors


def verify_live_pointer(live_link: Path, version: Path) -> list[str]:
    try:
        target = live_link.resolve(strict=True)
    except OSError as exc:
        return [f"live: symlink non risolvibile {live_link}: {exc}"]
    try:
        expected = version.resolve(strict=True)
    except OSError as exc:
        return [f"live: build attiva non risolvibile {version}: {exc}"]
    if target != expected:
        return [f"live: {live_link} -> {target}, atteso {expected}"]
    return []


def _docker_command(container: str, database: str, query: str) -> list[str]:
    inner = (
        f"docker exec -i -e PGUSER=postgres -e PGDATABASE={shlex.quote(database)} "
        f"{shlex.quote(container)} psql -X -t -A -F'|' -c {shlex.quote(query)}"
    )
    return ["sg", "docker", "-c", inner]


def database_datasets(
    *,
    container: str = DEFAULT_CONTAINER,
    database: str = DEFAULT_DATABASE,
) -> dict[str, dict[str, str]]:
    query = (
        "SELECT dataset_key, gtfs_schema, source_sha256 "
        "FROM public.gtfs_datasets WHERE is_active ORDER BY dataset_key;"
    )
    result = subprocess.run(
        _docker_command(container, database, query),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "lettura gtfs_datasets fallita: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    datasets: dict[str, dict[str, str]] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        key, schema, sha = (line.split("|") + ["", "", ""])[:3]
        datasets[key] = {"gtfs_schema": schema, "source_sha256": sha}
    if not datasets:
        raise RuntimeError("nessun dataset GTFS attivo nel database")
    return datasets


def database_route_count(
    database_datasets_map: Mapping[str, Mapping[str, Any]],
    *,
    container: str = DEFAULT_CONTAINER,
    database: str = DEFAULT_DATABASE,
) -> int:
    total = 0
    for row in database_datasets_map.values():
        schema = str(row.get("gtfs_schema") or "")
        if not schema or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_" for ch in schema):
            raise RuntimeError(f"schema GTFS non valido: {schema!r}")
        query = f'SELECT count(DISTINCT route_id) FROM "{schema}".trips;'
        result = subprocess.run(
            _docker_command(container, database, query),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"conteggio route fallito per {schema}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        total += int(result.stdout.strip() or "0")
    return total


def otp_graph(otp_url: str) -> dict[str, Any]:
    query = "{ feeds { feedId } routes { gtfsId } }"
    request = urllib.request.Request(
        f"{otp_url.rstrip('/')}/otp/gtfs/v1",
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # urllib errors are implementation-specific
        raise RuntimeError(f"OTP non raggiungibile su {otp_url}: {exc}") from exc
    if payload.get("errors"):
        raise RuntimeError(f"OTP GraphQL errors: {payload['errors']}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("OTP senza campo data")
    feeds = data.get("feeds")
    routes = data.get("routes")
    if not isinstance(feeds, list) or not isinstance(routes, list):
        raise RuntimeError("OTP senza feeds/routes")
    return {"feeds": feeds, "routes": routes}


def check_pipeline(
    *,
    state_file: Path = DEFAULT_STATE,
    result_file: Path = DEFAULT_RESULT,
    live_link: Path = DEFAULT_LIVE_LINK,
    otp_url: str = "http://127.0.0.1:8080",
    container: str = DEFAULT_CONTAINER,
    database: str = DEFAULT_DATABASE,
    check_otp: bool = True,
) -> list[str]:
    errors: list[str] = []
    state = load_json(state_file)
    result = load_json(result_file)
    if result.get("status") != "success":
        errors.append(f"last-result: status={result.get('status')!r}, atteso 'success'")

    db_datasets = database_datasets(container=container, database=database)
    state_datasets = state.get("datasets")
    if not isinstance(state_datasets, dict):
        errors.append("current.json: campo datasets assente o non oggetto")
        state_datasets = {}
    result_datasets = result.get("datasets")
    if not isinstance(result_datasets, dict):
        errors.append("last-result.json: campo datasets assente o non oggetto")
        result_datasets = {}

    errors.extend(compare_datasets(db_datasets, state_datasets, label="current.json"))
    errors.extend(compare_datasets(db_datasets, result_datasets, label="last-result.json"))

    version = Path(str(state.get("version") or ""))
    if not str(version):
        errors.append("current.json: version assente")
    else:
        errors.extend(
            verify_build_artifacts(
                version,
                db_datasets,
                graph_sha256=str(state.get("graph_sha256") or "") or None,
            )
        )
        errors.extend(verify_live_pointer(live_link, version))

    if check_otp:
        try:
            graph = otp_graph(otp_url)
        except RuntimeError as exc:
            errors.append(str(exc))
        else:
            if len(graph["feeds"]) < 2:
                errors.append(
                    f"OTP: {len(graph['feeds'])} feed esposti, attesi almeno 2"
                )
            expected_routes = database_route_count(
                db_datasets, container=container, database=database
            )
            actual_routes = len(graph["routes"])
            if actual_routes != expected_routes:
                errors.append(
                    f"OTP: {actual_routes} route esposte, attese {expected_routes} "
                    "dal database"
                )
    return errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--result-file", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--live-link", type=Path, default=DEFAULT_LIVE_LINK)
    parser.add_argument("--otp-url", default=os.environ.get("OTP_URL", "http://127.0.0.1:8080"))
    parser.add_argument(
        "--container",
        default=os.environ.get("POSTGRES_CONTAINER", DEFAULT_CONTAINER),
    )
    parser.add_argument(
        "--database", default=os.environ.get("POSTGRES_DB", DEFAULT_DATABASE)
    )
    parser.add_argument("--skip-otp", action="store_true", help="solo file e database")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        errors = check_pipeline(
            state_file=args.state_file,
            result_file=args.result_file,
            live_link=args.live_link,
            otp_url=args.otp_url,
            container=args.container,
            database=args.database,
            check_otp=not args.skip_otp,
        )
    except RuntimeError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("PIPELINE NON COERENTE:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "PIPELINE COERENTE: dataset DB = current.json = last-result.json, "
        "ZIP e graph.obj della build attiva allineati, symlink live corretto."
    )
    if not args.skip_otp:
        print("OTP: feed e numero route coerenti con il database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
