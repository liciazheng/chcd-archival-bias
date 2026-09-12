"""Synthetic CHCD-shaped fixtures.

CI does not download the 30 MB release, so the validation tests build tiny
files with the real column layout instead. Every fixture here is *valid*;
the tests break them one field at a time and assert that validation notices.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chcd.load import DELIMITER, NODE_COLUMNS, NODES_FILE, REL_COLUMNS, RELS_FILE

# (id, label, latitude, longitude, nationality) -- everything else stays empty.
_NODES = [
    ("0", "Person", "", "", "United States of America"),
    ("1", "Person", "", "", "Unknown"),
    ("2", "Person", "", "", "China"),
    ("3", "County", "31.230", "121.474", ""),
    ("4", "CorporateEntity", "", "", ""),
]

# (start_id, type, end_id, rel_type, start_year, end_year)
_RELS = [
    ("0", "PART_OF", "4", "Missionary", "1876", "1901"),
    ("1", "PRESENT_AT", "3", "Present at", "1900", ""),
    ("2", "INVOLVED_WITH", "4", "Signed Manifesto", "1950.0", "1950.0"),
]


def _row(columns: tuple[str, ...], values: dict[str, str]) -> str:
    return DELIMITER.join(values.get(column, "") for column in columns)


def write_dataset(directory: Path, *, nodes=None, rels=None) -> Path:
    """Write a synthetic node/rel pair into ``directory`` and return it."""
    nodes = _NODES if nodes is None else nodes
    rels = _RELS if rels is None else rels

    node_lines = [DELIMITER.join(NODE_COLUMNS)]
    for node_id, label, lat, lon, nationality in nodes:
        node_lines.append(
            _row(
                NODE_COLUMNS,
                {
                    ":ID": node_id,
                    ":LABEL": label,
                    "latitude": lat,
                    "longitude": lon,
                    "nationality": nationality,
                },
            )
        )

    rel_lines = [DELIMITER.join(REL_COLUMNS)]
    for start, type_, end, rel_type, start_year, end_year in rels:
        rel_lines.append(
            _row(
                REL_COLUMNS,
                {
                    ":START_ID": start,
                    ":TYPE": type_,
                    ":END_ID": end,
                    "rel_type": rel_type,
                    "start_year": start_year,
                    "end_year": end_year,
                },
            )
        )

    directory.mkdir(parents=True, exist_ok=True)
    (directory / NODES_FILE).write_text("\n".join(node_lines) + "\n", encoding="utf-8")
    (directory / RELS_FILE).write_text("\n".join(rel_lines) + "\n", encoding="utf-8")
    return directory


@pytest.fixture
def synthetic(tmp_path: Path) -> Path:
    """A small, structurally valid dataset."""
    return write_dataset(tmp_path / "raw")
