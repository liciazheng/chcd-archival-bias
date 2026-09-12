"""Loading and validating the CHCD v3.0.1 CSV release.

The upstream files are not ordinary CSVs and the differences matter enough
that every one of them is asserted here rather than left as a comment:

* the delimiter is ``@``, not a comma
* no field is quoted, and no cell anywhere in either file contains an ``@``,
  so the delimiter is genuinely unambiguous
* despite what the field looks like, there are no embedded newlines in either
  file -- ``chcd_v3.0.1_nodes.csv`` is 49,917 physical lines for 49,916 rows
* the longest single field is 2,342 characters, well under the stdlib csv
  limit, so ``csv.field_size_limit`` does not need raising

The one real parsing trap is that 6,721 ``start_year`` values arrive as
float-formatted strings (``"1950.0"``) while the rest are plain integers.
Naive ``int()`` raises on those; :func:`coerce_year` handles both.

Source: https://github.com/chcdatabase/data (CC BY 4.0)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"

NODES_FILE = "chcd_v3.0.1_nodes.csv"
RELS_FILE = "chcd_v3.0.1_rels.csv"

DELIMITER = "@"

#: Node labels present in v3.0.1, with the row count each one must have.
EXPECTED_NODE_COUNTS = {
    "Person": 37_392,
    "Institution": 7_039,
    "County": 2_889,
    "CorporateEntity": 1_213,
    "Publication": 430,
    "Prefecture": 337,
    "GeneralArea": 272,
    "Event": 163,
    "Township": 130,
    "Province": 40,
    "Village": 9,
    "Nation": 2,
}

#: Relationship types present in v3.0.1, with the row count each one must have.
#: The published documentation also lists ``CONNECTED_TO``; it does not occur
#: in the data. See docs/data-quality.md.
EXPECTED_REL_COUNTS = {
    "PRESENT_AT": 103_859,
    "PART_OF": 88_137,
    "LOCATED_IN": 20_531,
    "RELATED_TO": 8_445,
    "INSIDE_OF": 3_405,
    "INVOLVED_WITH": 2_148,
    "LINKED_TO": 141,
}

N_NODES = sum(EXPECTED_NODE_COUNTS.values())  # 49,916
N_RELS = sum(EXPECTED_REL_COUNTS.values())  # 226,666
#: The node table's 75 columns, in file order. Pinned by name rather than
#: count so that a re-ordered or renamed release fails loudly.
NODE_COLUMNS = (
    ":ID", ":LABEL", "chcd_id", "abbreviation", "alternative_chinese_name_hanzi",
    "alternative_chinese_name_romanized", "alternative_name_western", "baptism",
    "baptismal_name_western", "beatification", "beatification_date", "birth_day",
    "birth_month", "birth_place", "birth_year", "burial_place",
    "cannonization_date", "canonization", "china_start",
    "chinese_family_name_hanzi", "chinese_family_name_romanized",
    "chinese_given_name_hanzi", "chinese_given_name_romanized",
    "chinese_name_hanzi", "chinese_name_romanized", "christian_tradition",
    "circulation", "confirmation", "content", "corporate_entity_category",
    "corporate_entity_subcategory", "death_day", "death_month", "death_place",
    "death_year", "degree", "embarkment", "end_day", "end_month", "end_year",
    "event_category", "event_subcategory", "family_name_western", "format",
    "gender", "gender_served", "given_name_western", "institution_category",
    "institution_subcategory", "issue_frequency", "latitude", "longitude",
    "name_rom", "name_wes", "name_western", "name_zh", "nationality", "notes",
    "occupation", "ordination_archbishop", "ordination_bishop",
    "ordination_deacon", "ordination_priest", "other_abbreviation", "price",
    "publication_category", "publication_language", "publication_subcategory",
    "religious_family", "source", "start_day", "start_month", "start_year",
    "title", "vestition",
)

REL_COLUMNS = (
    ":START_ID", ":TYPE", ":END_ID", "chcd_start_id", "chcd_end_id", "rel_type",
    "start_day", "start_month", "start_year", "end_day", "end_month", "end_year",
    "notes", "source",
)

N_NODE_COLUMNS = len(NODE_COLUMNS)  # 75

#: Edges in v3.0.1 whose start_year is after their end_year. Known and small;
#: tracked so that a larger number fails validation instead of passing quietly.
N_REVERSED_EDGES = 14

#: Node labels that carry latitude/longitude. Every node with one of these
#: labels has coordinates; every node without one has none. Coverage is
#: structural, not partial -- see docs/data-quality.md.
GEOGRAPHIC_LABELS = frozenset(
    {"County", "Prefecture", "Township", "Province", "Village", "Nation"}
)

#: ``nationality`` is 98% non-empty, but a third of those cells hold this
#: literal string. Non-empty is not the same as known.
UNKNOWN_NATIONALITY = "Unknown"


class DataValidationError(ValueError):
    """Raised when a loaded file does not match the v3.0.1 release."""


def _read(path: Path) -> pd.DataFrame:
    """Read one CHCD CSV as all-strings, with only empty cells as missing.

    ``keep_default_na=False`` is deliberate: pandas would otherwise turn the
    strings ``"NA"``, ``"None"``, ``"null"`` and friends into missing values.
    In a dataset whose central finding is the difference between *absent* and
    *recorded as unknown*, that silent coercion would destroy the signal.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found -- run `python scripts/fetch_data.py` first"
        )
    return pd.read_csv(
        path,
        sep=DELIMITER,
        dtype=str,
        encoding="utf-8",
        keep_default_na=False,
        na_values=[""],
        engine="python",
    )


def coerce_year(series: pd.Series) -> pd.Series:
    """Parse a CHCD year column to nullable integers.

    Handles the mixed ``"1876"`` / ``"1950.0"`` formatting. Anything that is
    not a number becomes missing rather than raising, so that a single bad
    cell cannot take down a whole load; callers that care can compare
    ``series.notna()`` before and after.
    """
    return pd.to_numeric(series, errors="coerce").round().astype("Int64")


def load_nodes(raw_dir: Path | None = None) -> pd.DataFrame:
    """Load the node table, indexed by ``:ID``."""
    frame = _read((raw_dir or RAW_DIR) / NODES_FILE)
    # Only touch columns that are actually present, so that a renamed or
    # missing column surfaces as a validation error naming the column rather
    # than as a KeyError from inside the loader.
    for column in ("birth_year", "death_year", "start_year", "end_year"):
        if column in frame:
            frame[column] = coerce_year(frame[column])
    for column in ("latitude", "longitude"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_rels(raw_dir: Path | None = None) -> pd.DataFrame:
    """Load the relationship table.

    ``:TYPE`` holds the seven coarse categories; ``rel_type`` holds 1,412
    distinct free-text values describing the specific role. Both are kept --
    the free-text column is where the interesting detail lives.
    """
    frame = _read((raw_dir or RAW_DIR) / RELS_FILE)
    for column in ("start_year", "end_year"):
        if column in frame:
            frame[column] = coerce_year(frame[column])
    return frame


def validate_nodes(nodes: pd.DataFrame, *, strict: bool = True) -> None:
    """Check the node table against the v3.0.1 release.

    ``strict`` also pins the exact per-label row counts, which is what makes
    a silently truncated or re-versioned download fail loudly instead of
    producing plausible-looking but wrong analysis.
    """
    if tuple(nodes.columns) != NODE_COLUMNS:
        got = tuple(nodes.columns)
        detail = (
            f"got {len(got)} columns, expected {N_NODE_COLUMNS}"
            if len(got) != N_NODE_COLUMNS
            else f"differs at: {sorted(set(got) ^ set(NODE_COLUMNS))}"
        )
        raise DataValidationError(
            f"node columns do not match v3.0.1 -- {detail}. "
            "A single-column result usually means the wrong delimiter."
        )
    if nodes[":ID"].duplicated().any():
        dupes = nodes.loc[nodes[":ID"].duplicated(), ":ID"].head(5).tolist()
        raise DataValidationError(f"duplicate :ID values, e.g. {dupes}")
    if nodes[":ID"].isna().any():
        raise DataValidationError("some nodes have no :ID")

    labels = set(nodes[":LABEL"].dropna().unique())
    if unknown := labels - set(EXPECTED_NODE_COUNTS):
        raise DataValidationError(f"unexpected node labels: {sorted(unknown)}")

    # Coordinates are all-or-nothing per label. If that ever stops holding,
    # every geographic claim in the analysis needs revisiting.
    has_coords = nodes["latitude"].notna()
    geographic = nodes[":LABEL"].isin(GEOGRAPHIC_LABELS)
    bad = int((has_coords & ~geographic).sum())
    missing = int((~has_coords & geographic).sum())
    if bad or missing:
        raise DataValidationError(
            f"coordinate coverage is no longer structural: {bad} non-geographic "
            f"nodes have coordinates, {missing} geographic nodes lack them"
        )

    if not strict:
        return
    counts = nodes[":LABEL"].value_counts().to_dict()
    if counts != EXPECTED_NODE_COUNTS:
        raise DataValidationError(
            f"node counts do not match v3.0.1\n"
            f"  expected: {EXPECTED_NODE_COUNTS}\n  got:      {counts}"
        )


def validate_rels(
    rels: pd.DataFrame, nodes: pd.DataFrame | None = None, *, strict: bool = True
) -> None:
    """Check the relationship table, optionally against the node table."""
    if tuple(rels.columns) != REL_COLUMNS:
        raise DataValidationError(
            f"relationship columns do not match v3.0.1: {tuple(rels.columns)}"
        )

    types = set(rels[":TYPE"].dropna().unique())
    if unknown := types - set(EXPECTED_REL_COUNTS):
        raise DataValidationError(f"unexpected relationship types: {sorted(unknown)}")

    both = rels["start_year"].notna() & rels["end_year"].notna()
    reversed_ = int((both & (rels["start_year"] > rels["end_year"])).sum())
    if reversed_ > N_REVERSED_EDGES:
        raise DataValidationError(
            f"{reversed_} edges end before they start "
            f"(v3.0.1 has exactly {N_REVERSED_EDGES})"
        )

    if nodes is not None:
        ids = set(nodes[":ID"])
        for column in (":START_ID", ":END_ID"):
            if dangling := int((~rels[column].isin(ids)).sum()):
                raise DataValidationError(
                    f"{dangling} edges have a {column} with no matching node"
                )

    if not strict:
        return
    counts = rels[":TYPE"].value_counts().to_dict()
    if counts != EXPECTED_REL_COUNTS:
        raise DataValidationError(
            f"relationship counts do not match v3.0.1\n"
            f"  expected: {EXPECTED_REL_COUNTS}\n  got:      {counts}"
        )


def load(raw_dir: Path | None = None, *, validate: bool = True, strict: bool = True):
    """Load and validate both tables. Returns ``(nodes, rels)``."""
    nodes = load_nodes(raw_dir)
    rels = load_rels(raw_dir)
    if validate:
        validate_nodes(nodes, strict=strict)
        validate_rels(rels, nodes, strict=strict)
    return nodes, rels
