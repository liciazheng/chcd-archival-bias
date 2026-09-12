"""Checks against the actual v3.0.1 download.

Skipped when data/raw is empty, which is the case in CI -- these assert the
published facts of the release, so they are the ones that catch an upstream
re-publication under the same version number.
"""

from __future__ import annotations

import pytest

from chcd.load import (
    EXPECTED_NODE_COUNTS,
    EXPECTED_REL_COUNTS,
    GEOGRAPHIC_LABELS,
    N_NODES,
    N_RELS,
    NODES_FILE,
    RAW_DIR,
    RELS_FILE,
    load,
)

pytestmark = [
    pytest.mark.realdata,
    pytest.mark.skipif(
        not (RAW_DIR / NODES_FILE).exists() or not (RAW_DIR / RELS_FILE).exists(),
        reason="CHCD download absent -- run `python scripts/fetch_data.py`",
    ),
]


@pytest.fixture(scope="module")
def data():
    return load()  # strict validation on by default


def test_release_scale(data):
    nodes, rels = data
    assert len(nodes) == N_NODES == 49_916
    assert len(rels) == N_RELS == 226_666


def test_node_and_relationship_counts(data):
    nodes, rels = data
    assert nodes[":LABEL"].value_counts().to_dict() == EXPECTED_NODE_COUNTS
    assert rels[":TYPE"].value_counts().to_dict() == EXPECTED_REL_COUNTS


def test_documented_connected_to_type_is_absent(data):
    """The data documentation lists eight relationship types; there are seven."""
    _, rels = data
    assert "CONNECTED_TO" not in set(rels[":TYPE"])


def test_time_lives_on_the_edges(data):
    """92% of edges are dated. That is the project's main analytic dimension."""
    _, rels = data
    dated = (rels["start_year"].notna() | rels["end_year"].notna()).sum()
    assert dated == 207_831
    assert dated / len(rels) > 0.91


def test_coordinates_cover_every_geographic_node(data):
    """3,407 nodes have coordinates -- all of them, and only them, geographic.

    This is why the analysis needs no external gazetteer: resolving a person
    to a County resolves them to a point.
    """
    nodes, _ = data
    with_coords = nodes[nodes["latitude"].notna()]
    assert len(with_coords) == 3_407
    assert set(with_coords[":LABEL"]) == GEOGRAPHIC_LABELS
    for label in GEOGRAPHIC_LABELS:
        of_label = nodes[nodes[":LABEL"] == label]
        assert of_label["latitude"].notna().all(), f"{label} has gaps"
    assert with_coords["latitude"].between(15, 55).all()
    assert with_coords["longitude"].between(70, 140).all()


def test_hanzi_names_live_in_the_split_columns(data):
    """chinese_name_hanzi and name_zh are entirely empty; don't analyse them."""
    nodes, _ = data
    people = nodes[nodes[":LABEL"] == "Person"]
    assert people["chinese_name_hanzi"].notna().sum() == 0
    assert people["name_zh"].notna().sum() == 0
    assert people["chinese_family_name_hanzi"].notna().sum() == 12_260
    assert people["chinese_given_name_hanzi"].notna().sum() == 9_888


def test_unknown_nationality_is_a_recorded_value_not_a_gap(data):
    """98% non-empty, but a third of that is the literal string 'Unknown'."""
    nodes, _ = data
    people = nodes[nodes[":LABEL"] == "Person"]
    assert (people["nationality"] == "Unknown").sum() == 11_414
    assert people["nationality"].notna().sum() == 36_537


def test_the_headline_imbalance(data):
    """A database of Christianity in China holds 4x more Americans than Chinese."""
    nodes, _ = data
    counts = nodes[nodes[":LABEL"] == "Person"]["nationality"].value_counts()
    assert counts["United States of America"] == 9_997
    assert counts["China"] == 2_492


def test_most_chinese_people_arrive_via_one_1950_document(data):
    """1,486 of 2,492 Chinese people enter through the Three-Self Manifesto.

    Any 'Chinese share rises over time' series is dominated by this single
    source, so the analysis has to separate it out explicitly.
    """
    nodes, rels = data
    people = nodes[nodes[":LABEL"] == "Person"]
    chinese = set(people.loc[people["nationality"] == "China", ":ID"])

    manifesto = rels[rels["rel_type"] == "Signed Manifesto"]
    signatories = set(manifesto[":START_ID"]) | set(manifesto[":END_ID"])
    signatories &= set(people[":ID"])

    assert len(manifesto) == 1_486
    assert len(signatories) == 1_486
    assert signatories <= chinese, "every signatory is recorded as Chinese"
    assert len(signatories) / len(chinese) > 0.59


def test_person_to_mission_society_link_is_well_populated(data):
    """86% of people attach to a CorporateEntity, and 97% of those edges are dated.

    This is the backbone of the per-society bias comparison.
    """
    nodes, rels = data
    people = set(nodes.loc[nodes[":LABEL"] == "Person", ":ID"])
    societies = set(nodes.loc[nodes[":LABEL"] == "CorporateEntity", ":ID"])

    edges = rels[
        (rels[":START_ID"].isin(people) & rels[":END_ID"].isin(societies))
        | (rels[":END_ID"].isin(people) & rels[":START_ID"].isin(societies))
    ]
    assert len(edges) == 79_964
    assert set(edges[":TYPE"]) == {"PART_OF"}

    linked = (set(edges[":START_ID"]) | set(edges[":END_ID"])) & people
    assert len(linked) == 32_276
    assert len(linked) / len(people) > 0.86

    dated = (edges["start_year"].notna() | edges["end_year"].notna()).sum()
    assert dated / len(edges) > 0.97


def test_float_formatted_years_were_parsed_not_dropped(data):
    """6,721 start_year cells arrive as '1950.0'. They must survive loading."""
    _, rels = data
    assert rels["start_year"].notna().sum() == 201_011 + 6_721
    assert (rels["start_year"] == 1950).sum() == 10_174 + 5_000
