"""Unit tests for the explicit GTFS -> database -> OTP identifier mapping."""

from __future__ import annotations

import pytest

from app.services.agents.mobility.gtfs_ids import (
    is_feed_scoped_id,
    otp_id,
    parse_otp_id,
)


def test_otp_id_roundtrip() -> None:
    assert otp_id("42", "route:2") == "42:route:2"
    assert parse_otp_id("42:route:2") == ("42", "route:2")


def test_feed_id_is_required_and_not_hardcoded() -> None:
    with pytest.raises(ValueError):
        otp_id("", "2")
    with pytest.raises(ValueError):
        otp_id("feed:1", "2")


def test_unscoped_ids_are_rejected() -> None:
    assert is_feed_scoped_id("1:2") is True
    assert is_feed_scoped_id("2") is False
    assert is_feed_scoped_id(":2") is False
    assert is_feed_scoped_id("1:") is False
