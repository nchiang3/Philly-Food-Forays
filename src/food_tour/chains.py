"""Show one location per chain restaurant (for example, a single Wawa)."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Hashable
from typing import Any

from .distance import closest_to, leading_points, select_close_together


CHAIN_LOCATIONS_COLUMN = "chain locations"

# How many other top restaurants a chain location is compared against when
# there are no tour stops yet to measure from.
REFERENCE_COUNT = 10


def chain_key(name: str) -> str:
    """Normalize a restaurant name so locations of one chain share a key.

    Matching ignores case, accents, apostrophes, punctuation, a leading
    "The", and "&" versus "and", so "WAWA", "Wawa" and "Pat's King of Steaks"
    versus "Pats King Of Steaks" match.
    """
    text = unicodedata.normalize("NFKD", name)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold().replace("&", " and ")
    text = re.sub(r"['’]", "", text)
    text = re.sub(r"[^0-9a-z]+", " ", text).strip()
    return re.sub(r"^the ", "", text)


def row_chain_key(row: dict[str, Any]) -> Hashable:
    """Chain key for a row; rows without a usable name never merge."""
    key = chain_key(str(row.get("name") or ""))
    return key if key else ("unnamed", id(row))


def _location_counts(rows: list[dict[str, Any]]) -> dict[Hashable, int]:
    counts: dict[Hashable, int] = {}
    for row in rows:
        key = row_chain_key(row)
        counts[key] = counts.get(key, 0) + 1
    return counts


def collapse_chains(
    ranked: list[dict[str, Any]], reference_count: int = REFERENCE_COUNT
) -> list[dict[str, Any]]:
    """Keep one location per chain, choosing the one nearest the other picks.

    A chain keeps the rank of its best-ranked location. The location shown is
    the one with the smallest average straight-line distance to the
    best-ranked location of each of the top ``reference_count`` other
    restaurants or chains, so it sits closest to the rest of the tour. Ties go
    to the better-ranked location. Every row gains a ``chain locations``
    column counting the matching locations that were merged.
    """
    groups: dict[Hashable, list[dict[str, Any]]] = {}
    for row in ranked:
        groups.setdefault(row_chain_key(row), []).append(row)

    collapsed: list[dict[str, Any]] = []
    for key, locations in groups.items():
        if len(locations) == 1:
            chosen = locations[0]
        else:
            points = leading_points(ranked, row_chain_key, key, reference_count)
            chosen = closest_to(locations, points)
        collapsed.append({**chosen, CHAIN_LOCATIONS_COLUMN: len(locations)})
    return collapsed


def select_close_together_one_per_chain(
    ranked: list[dict[str, Any]],
    max_miles: float,
    max_stops: int | None = None,
    reference_count: int = REFERENCE_COUNT,
) -> list[dict[str, Any]]:
    """Close-together tour that uses at most one location of each chain.

    Each chain is considered at the rank of its best location. Among its
    locations within ``max_miles`` of every stop already chosen, the one with
    the smallest average distance to those stops joins the tour, so a chain is
    only skipped when none of its locations fit.
    """
    tour = select_close_together(
        ranked,
        max_miles,
        max_stops,
        group_key=row_chain_key,
        reference_count=reference_count,
    )
    counts = _location_counts(ranked)
    return [
        {**row, CHAIN_LOCATIONS_COLUMN: counts.get(row_chain_key(row), 1)}
        for row in tour
    ]


def merged_chain_count(rows: list[dict[str, Any]]) -> int:
    """Number of rows that stand in for more than one chain location."""
    return sum(row.get(CHAIN_LOCATIONS_COLUMN, 1) > 1 for row in rows)
