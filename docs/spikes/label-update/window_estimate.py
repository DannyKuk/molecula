"""How many drugs would a label update fetch again, and how much would it download? (#341)

Compares a window on openFDA's `effective_time` with checks on the store's own labels. Reads the
store read-only, sends a few count queries to openFDA (no API key needed) and sizes each marked
drug's re-fetch by its label pages in the store's HTTP cache.

    cd backend
    OFFLINE=0 uv run python ../docs/spikes/label-update/window_estimate.py ../data/build/molecula.db
"""

import re
import sqlite3
import sys
import urllib.parse
from datetime import date, timedelta

from molecula.sources.http import SourceClient
from molecula.sources.openfda import LABELS, CountPage, OpenFdaClient
from molecula.sources.parsing import parse
from molecula.store.compounds import CompoundStore
from molecula.store.http_cache import HttpCache
from molecula.store.labels import LabelStore
from molecula.store.schema import ensure_schema

COMBINATION = re.compile(r",|/|\bAND\b|\bWITH\b", re.IGNORECASE)
MARGINS = (30, 60, 90)


def cached_pages(store: sqlite3.Connection) -> dict[str, tuple[int, float]]:
    """Label pages and megabytes per drug name in the store's HTTP cache."""
    pages: dict[str, tuple[int, float]] = {}
    rows = store.execute(
        "SELECT url, length(body) FROM http_cache WHERE url LIKE '%api.fda.gov%generic_name%'"
    )
    for url, size in rows:
        search = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["search"][0]
        name = search.removeprefix('openfda.generic_name:"').removesuffix('"')
        count, megabytes = pages.get(name, (0, 0.0))
        pages[name] = (count + 1, megabytes + size / 1e6)
    return pages


def recent_single_ingredient_names(http: SourceClient, names: list[str], since: date) -> list[str]:
    found: list[str] = []
    for start in range(0, len(names), 30):
        quoted = " ".join(f'"{name}"' for name in names[start : start + 30])
        params = {
            "search": f"openfda.generic_name:({quoted}) AND effective_time:[{since:%Y%m%d} TO *]",
            "count": "openfda.generic_name.exact",
            "limit": "1000",
        }
        page = parse(http.get(LABELS, params=params, refresh=True), CountPage)
        found += [term.term for term in page.results if not COMBINATION.search(term.term)]
    return found


def main(db_path: str) -> None:
    store = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    compounds = CompoundStore(store).all()
    labels = {compound.cid: LabelStore(store).get(compound.cid) for compound in compounds}
    times = {label.set_id: label.effective_time for drug in labels.values() for label in drug}
    oldest_fetch = store.execute("SELECT MIN(fetched_at) FROM label").fetchone()[0]
    pages = cached_pages(store)
    scratch = sqlite3.connect(":memory:")
    ensure_schema(scratch)
    http = SourceClient(HttpCache(scratch), offline=False)
    openfda = OpenFdaClient(http)

    listed = openfda.listed(sorted(times))
    newer = openfda.newer(dict(sorted(times.items())))
    own = [
        compound.name
        for compound in compounds
        if any(
            label.set_id not in listed or label.set_id in newer for label in labels[compound.cid]
        )
    ]
    print(f"{len(compounds)} drugs, {len(times)} labels, fetched from {oldest_fetch[:10]}")
    print(
        f"own labels: {len(times) - len(listed)} withdrawn, {len(newer)} newer -> {len(own)} drugs"
    )
    for margin in MARGINS:
        since = date.fromisoformat(oldest_fetch[:10]) - timedelta(days=margin)
        recent = recent_single_ingredient_names(http, [c.name for c in compounds], since)
        marked = [
            compound.name
            for compound in compounds
            if any(re.search(rf"\b{re.escape(compound.name)}\b", n, re.I) for n in recent)
        ]
        count = sum(pages.get(name, (1, 0.0))[0] for name in marked)
        megabytes = sum(pages.get(name, (0, 0.0))[1] for name in marked)
        print(
            f"window from {since} ({margin} days before the fetch): {len(marked)} drugs, "
            f"{count} label pages, {megabytes:,.0f} MB"
        )


if __name__ == "__main__":
    main(sys.argv[1])
