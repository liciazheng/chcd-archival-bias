# Archival bias in the China Historical Christian Database

A database of Christianity **in China**, covering 1550–1950, records 9,997 Americans
and 2,492 Chinese people.

That ratio is the subject of this project. It is not a claim about who was actually
there — it is a measurement of who the mission archives chose to write down. This
repository builds the tooling to quantify that bias: how large it is, how it moves
over time, and which missions record more carefully than others.

All figures below were computed from the release itself, not copied from its
documentation. Every count is pinned in the loader and re-checked by the test suite.

## The data

[CHCD v3.0.1](https://github.com/chcdatabase/data), published by the Center for
Global Christianity and Mission at Boston University, under CC BY 4.0.

| | |
|---|---|
| Nodes | 49,916 across 12 labels (37,392 of them people) |
| Relationships | 226,666 across 7 types |
| Columns in the node table | 75 |
| Span of dated edges | 935–2016 |

**The time dimension lives on the edges, not the nodes.** 207,831 relationships
(91.7%) carry a `start_year` or an `end_year`, against only 21.1% of people who
have a birth or death year. "When was this person at this institution" is far
better recorded than "when was this person alive", which makes the edge table the
backbone of any temporal analysis here.

## What the record skew looks like

Nationality, among the 37,392 people:

| Nationality | People | Share |
|---|---:|---:|
| Unknown | 11,414 | 30.5% |
| United States of America | 9,997 | 26.7% |
| Britain | 4,136 | 11.1% |
| **China** | **2,492** | **6.7%** |
| France | 1,688 | 4.5% |
| Germany | 1,422 | 3.8% |
| Canada | 982 | 2.6% |
| Italy | 924 | 2.5% |

Four American names for every Chinese one. A second, independent measurement points
the same way: only 32.8% of people have a Chinese-character name recorded at all.

The explanation is in how the records were made. These archives were compiled by
sending missions, which registered their own personnel in detail and noted Chinese
converts, catechists and local preachers only in passing. The skew is a property of
the *record-keeping*, and reading it as a fact about Chinese Christianity would
invert what the data actually says.

This is measurable rather than merely assertable: group by decade, by sending body
(`CorporateEntity`), and by `christian_tradition`, then track the Chinese share and
the field-completeness rate across those groups.

## Known data limitations

Each of these was confirmed against the release and is asserted in the loader, so a
future version that no longer behaves this way fails the tests instead of quietly
producing different numbers.

**The delimiter is `@`, not a comma.** No cell in either file contains one, so the
split is unambiguous — but a default `read_csv` returns a single column.

**`nationality` is 97.7% non-empty, and a third of that is the literal string
`"Unknown"`** (11,414 people). Non-empty is not the same as known; treating it as
coverage overstates what the archive records by a factor of three.

**`chinese_name_hanzi` and `name_zh` are entirely empty** — 0 rows each, despite
being the two fields whose names suggest otherwise. Chinese characters live in
`chinese_family_name_hanzi` (12,260) and `chinese_given_name_hanzi` (9,888).

**Several promising fields are effectively absent:** `occupation` 1.2%,
`china_start` 5 rows, `birth_year` 16.6%, `death_year` 19.3%. By contrast `gender`
is 100% and `christian_tradition` 64.3%.

**Coordinates are structural, not partial.** 3,407 nodes carry a latitude, and they
are exactly the six geographic labels — every County, Prefecture, Township,
Province, Village and Nation has one; no Person or Institution does. Placing an
institution on a map means joining through `LOCATED_IN`, and a historical gazetteer
would be needed for anything finer.

**The documentation lists a relationship type the data does not contain.**
`CONNECTED_TO` appears in the published schema; the release has seven types and
that is not one of them.

**6,721 `start_year` values arrive as `"1950.0"`** while the rest are plain
integers, so a naive `int()` raises partway through the file.

**14 edges end before they start.** Small and known; the loader fails if that count
ever grows.

## What is here

The data layer, tested and reproducible:

- `src/chcd/load.py` — reads both tables, coerces the mixed-format year columns,
  and validates the result against v3.0.1: exact column names in file order,
  per-label and per-type row counts, no duplicate or missing IDs, no dangling edge
  endpoints, structural coordinate coverage.
- `scripts/fetch_data.py` — pulls the two V3 files (30 MB) rather than cloning the
  full 360 MB upstream repository, and can print SHA-256 checksums.
- `tests/` — 15 tests against synthetic files with the real column layout, plus 11
  marked `realdata` that assert the published counts against an actual download.
- CI on Python 3.11, 3.12 and 3.13, with the upstream verification split into its
  own job so that a change at the source is distinguishable from a bug here.

The analysis and its figures are not written yet. This README will carry the
findings as they land.

## Reproducing

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows
python scripts/fetch_data.py                      # 30 MB into data/raw/
pytest                                            # all 26 tests
```

`data/raw/` is not tracked. Without it the 11 `realdata` tests skip themselves and
the other 15 still run.

## Source and attribution

China Historical Christian Database, v3.0.1. Center for Global Christianity and
Mission, Boston University. Licensed CC BY 4.0.

- Data: <https://github.com/chcdatabase/data>
- Documentation: <https://chcdatabase.github.io/data-documentation/>
- Dataset paper: <https://doi.org/10.3390/data9060076>

The upstream repository carries no `LICENSE` file; the CC BY 4.0 terms are stated
on the project site and in the paper.
