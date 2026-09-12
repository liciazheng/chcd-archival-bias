"""Validation tests: feed known-bad data in, assert it is rejected."""

from __future__ import annotations

import pandas as pd
import pytest

from chcd.load import (
    NODES_FILE,
    RELS_FILE,
    DataValidationError,
    coerce_year,
    load,
    load_nodes,
    load_rels,
    validate_nodes,
    validate_rels,
)
from conftest import write_dataset

# --------------------------------------------------------------------------
# year coercion -- the one real parsing trap in the upstream files
# --------------------------------------------------------------------------

def test_coerce_year_handles_both_upstream_formats():
    """6,721 start_year cells are float-formatted; the rest are plain ints."""
    result = coerce_year(pd.Series(["1876", "1950.0", "", None, "circa 1900"]))
    assert result.tolist()[:2] == [1876, 1950]
    assert result.isna().tolist() == [False, False, True, True, True]
    assert result.dtype == "Int64"


def test_coerce_year_is_not_lossy_on_plain_integers():
    years = [str(y) for y in range(1550, 1951)]
    assert coerce_year(pd.Series(years)).tolist() == list(range(1550, 1951))


# --------------------------------------------------------------------------
# the happy path
# --------------------------------------------------------------------------

def test_synthetic_dataset_loads_and_validates(synthetic):
    nodes, rels = load(synthetic, strict=False)
    assert len(nodes) == 5
    assert len(rels) == 3
    assert rels["start_year"].tolist() == [1876, 1900, 1950]


def test_literal_unknown_survives_loading(synthetic):
    """'Unknown' must stay a value, not become a missing cell.

    The whole argument of the project rests on the difference between a
    nationality that was never recorded and one recorded as unknown.
    """
    nodes = load_nodes(synthetic)
    assert (nodes["nationality"] == "Unknown").sum() == 1
    assert nodes["nationality"].isna().sum() == 2  # the County and CorporateEntity


def test_missing_download_names_the_fetch_script(tmp_path):
    with pytest.raises(FileNotFoundError, match="fetch_data.py"):
        load_nodes(tmp_path)


# --------------------------------------------------------------------------
# broken data must be rejected
# --------------------------------------------------------------------------

def test_duplicate_node_ids_rejected(tmp_path):
    raw = write_dataset(
        tmp_path / "raw",
        nodes=[
            ("0", "Person", "", "", "China"),
            ("0", "Person", "", "", "China"),
        ],
        rels=[],
    )
    with pytest.raises(DataValidationError, match="duplicate :ID"):
        validate_nodes(load_nodes(raw), strict=False)


def test_unexpected_node_label_rejected(tmp_path):
    raw = write_dataset(
        tmp_path / "raw", nodes=[("0", "Spaceship", "", "", "")], rels=[]
    )
    with pytest.raises(DataValidationError, match="unexpected node labels"):
        validate_nodes(load_nodes(raw), strict=False)


def test_unexpected_relationship_type_rejected(tmp_path):
    """The docs list CONNECTED_TO; the data does not contain it.

    If a future release introduces it, this is where we find out.
    """
    raw = write_dataset(
        tmp_path / "raw",
        nodes=[("0", "Person", "", "", ""), ("1", "Person", "", "", "")],
        rels=[("0", "CONNECTED_TO", "1", "", "", "")],
    )
    with pytest.raises(DataValidationError, match="CONNECTED_TO"):
        validate_rels(load_rels(raw), strict=False)


def test_dangling_edge_rejected(tmp_path):
    raw = write_dataset(
        tmp_path / "raw",
        nodes=[("0", "Person", "", "", "")],
        rels=[("0", "PART_OF", "999", "", "", "")],
    )
    nodes, rels = load_nodes(raw), load_rels(raw)
    with pytest.raises(DataValidationError, match="no matching node"):
        validate_rels(rels, nodes, strict=False)


def test_person_with_coordinates_rejected(tmp_path):
    """Coordinates are structural: geographic labels have them, others never do.

    Every spatial claim in the analysis resolves a Person to a County to get
    a location. If a Person ever carries its own coordinates, that reasoning
    silently stops being correct -- so it has to fail here instead.
    """
    raw = write_dataset(
        tmp_path / "raw", nodes=[("0", "Person", "31.230", "121.474", "")], rels=[]
    )
    with pytest.raises(DataValidationError, match="no longer structural"):
        validate_nodes(load_nodes(raw), strict=False)


def test_county_without_coordinates_rejected(tmp_path):
    raw = write_dataset(tmp_path / "raw", nodes=[("0", "County", "", "", "")], rels=[])
    with pytest.raises(DataValidationError, match="no longer structural"):
        validate_nodes(load_nodes(raw), strict=False)


def test_wrong_delimiter_is_caught(tmp_path):
    """Reading the '@' file as a comma CSV collapses it to one column."""
    raw = write_dataset(tmp_path / "raw")
    misread = pd.read_csv(raw / NODES_FILE, sep=",", dtype=str)
    assert misread.shape[1] == 1, "sanity: comma parsing should give one column"
    with pytest.raises(DataValidationError, match="delimiter"):
        validate_nodes(misread, strict=False)


def test_truncated_download_fails_strict_validation(synthetic):
    """Strict mode pins exact counts, so a partial file cannot pass unnoticed."""
    with pytest.raises(DataValidationError, match="node counts do not match"):
        validate_nodes(load_nodes(synthetic), strict=True)


def test_reversed_year_range_rejected(tmp_path):
    raw = write_dataset(
        tmp_path / "raw",
        nodes=[("0", "Person", "", "", ""), ("1", "Person", "", "", "")],
        rels=[
            ("0", "PART_OF", "1", "", "1900", "1880") for _ in range(20)
        ],
    )
    with pytest.raises(DataValidationError, match="end before they start"):
        validate_rels(load_rels(raw), strict=False)


def test_renamed_column_rejected(tmp_path):
    raw = write_dataset(tmp_path / "raw")
    text = (raw / RELS_FILE).read_text(encoding="utf-8")
    (raw / RELS_FILE).write_text(text.replace("start_year", "begin_year", 1), "utf-8")
    with pytest.raises(DataValidationError, match="relationship columns"):
        validate_rels(load_rels(raw), strict=False)
