"""Unit tests for the read-only DB/OTP pipeline consistency checker."""

from __future__ import annotations

import hashlib
from pathlib import Path

from infra.otp.check_pipeline_consistency import (
    compare_datasets,
    verify_build_artifacts,
    verify_live_pointer,
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_compare_datasets_detects_hash_schema_and_key_differences() -> None:
    database = {
        "anm": {"gtfs_schema": "gtfs_anm", "source_sha256": "aaa"},
        "eav": {"gtfs_schema": "gtfs_eav", "source_sha256": "bbb"},
    }
    assert compare_datasets(database, database, label="current") == []

    errors = compare_datasets(
        database,
        {
            "anm": {"gtfs_schema": "gtfs_anm", "source_sha256": "different"},
            "eav": {"gtfs_schema": "gtfs_wrong", "source_sha256": "bbb"},
        },
        label="current",
    )
    assert any("hash diverso" in error for error in errors)
    assert any("schema diverso" in error for error in errors)

    errors = compare_datasets(database, {"anm": database["anm"]}, label="last")
    assert any("dataset diversi" in error for error in errors)


def test_verify_build_artifacts_matches_zips_and_graph(tmp_path: Path) -> None:
    build = tmp_path / "graph-test"
    otp_data = build / "otp-data"
    otp_data.mkdir(parents=True)
    anm = b"anm-zip"
    eav = b"eav-zip"
    graph = b"graph-obj"
    (otp_data / "anm.gtfs.zip").write_bytes(anm)
    (otp_data / "eav.gtfs.zip").write_bytes(eav)
    (otp_data / "graph.obj").write_bytes(graph)
    database = {
        "anm": {"gtfs_schema": "gtfs_anm", "source_sha256": _sha(anm)},
        "eav": {"gtfs_schema": "gtfs_eav", "source_sha256": _sha(eav)},
    }

    assert verify_build_artifacts(build, database, graph_sha256=_sha(graph)) == []

    (otp_data / "eav.gtfs.zip").write_bytes(b"changed")
    errors = verify_build_artifacts(build, database, graph_sha256=_sha(graph))
    assert any("hash ZIP diverso per 'eav'" in error for error in errors)


def test_verify_build_artifacts_reports_missing_graph(tmp_path: Path) -> None:
    build = tmp_path / "graph-test"
    (build / "otp-data").mkdir(parents=True)
    errors = verify_build_artifacts(build, {}, graph_sha256=None)
    assert any("graph.obj assente" in error for error in errors)


def test_verify_live_pointer(tmp_path: Path) -> None:
    build = tmp_path / "graph-a"
    build.mkdir()
    other = tmp_path / "graph-b"
    other.mkdir()
    link = tmp_path / "otp-live"
    link.symlink_to(build)

    assert verify_live_pointer(link, build) == []
    errors = verify_live_pointer(link, other)
    assert errors and "atteso" in errors[0]
