"""Map OTP feeds to configured GTFS datasets without assuming feed IDs.

OTP assigns ``feedId`` values when it builds a graph. The only stable link
between an OTP feed and a persisted dataset is the set of GTFS agency IDs it
contains, because those IDs are stored in ``public.gtfs_datasets.agency_ids``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _agency_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {part.strip() for part in value.split(",") if part.strip()}
    if isinstance(value, Iterable):
        return {str(part).strip() for part in value if str(part).strip()}
    return {str(value).strip()}


def map_feeds_to_datasets(
    feed_agencies: Mapping[str, Iterable[str]],
    datasets: Iterable[Mapping[str, Any]],
) -> dict[str, str]:
    """Return ``feedId -> dataset_key`` using agency IDs as the only key.

    Raises ``ValueError`` when a feed contains agencies from zero or more than
    one dataset, or when a dataset has no identifiable agency. Such a state is
    ambiguous and must not be resolved by guessing a feed number.
    """
    by_agency: dict[str, set[str]] = {}
    for dataset in datasets:
        key = str(dataset.get("dataset_key") or "").strip()
        if not key:
            raise ValueError("dataset GTFS senza dataset_key")
        agencies = _agency_set(dataset.get("agency_ids"))
        if not agencies:
            raise ValueError(f"dataset '{key}' senza agency_ids")
        for agency_id in agencies:
            by_agency.setdefault(agency_id, set()).add(key)

    mapping: dict[str, str] = {}
    for feed_id, agencies in feed_agencies.items():
        normalized = {str(agency).strip() for agency in agencies if str(agency).strip()}
        if not normalized:
            raise ValueError(f"feed OTP '{feed_id}' senza agencies")
        candidates: set[str] = set()
        for agency_id in normalized:
            candidates.update(by_agency.get(agency_id, set()))
        if len(candidates) != 1:
            raise ValueError(
                f"feed OTP '{feed_id}' ambiguo: agencies={sorted(normalized)} "
                f"candidati={sorted(candidates)}"
            )
        mapping[str(feed_id)] = candidates.pop()
    return mapping


__all__ = ["map_feeds_to_datasets"]
