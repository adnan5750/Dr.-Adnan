#!/usr/bin/env python3
"""
Sync publications into data/publications.json.

Primary source : Google Scholar via SerpAPI (needs SERPAPI_KEY env var).
Fallback       : ORCID public API (no key needed).
DOIs from ORCID are merged into Scholar entries by title match.

Safety: if every source fails, or the new list is suspiciously short,
the existing JSON is left untouched and the script exits non-zero.
"""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests

SCHOLAR_ID = "IPrRziQAAAAJ"
ORCID_ID = "0000-0001-9224-3824"
OUT = Path(__file__).resolve().parents[1] / "data" / "publications.json"
TIMEOUT = 60


def norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- Scholar
def fetch_scholar(api_key: str):
    pubs, profile, start, page = [], {}, 0, 100
    while True:
        r = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_scholar_author",
                "author_id": SCHOLAR_ID,
                "api_key": api_key,
                "hl": "en",
                "sort": "pubdate",
                "num": page,
                "start": start,
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(data["error"])

        if start == 0:
            for row in data.get("cited_by", {}).get("table", []):
                for key, val in row.items():  # citations / h_index / i10_index
                    profile[key] = to_int(val.get("all"))

        articles = data.get("articles", [])
        for a in articles:
            pubs.append({
                "title": a.get("title", "").strip(),
                "authors": a.get("authors", ""),
                "venue": a.get("publication", ""),
                "year": to_int(a.get("year")),
                "citations": to_int((a.get("cited_by") or {}).get("value")) or 0,
                "url": a.get("link", ""),
                "doi": "",
            })
        if len(articles) < page:
            break
        start += page
    return pubs, profile


# ---------------------------------------------------------------- ORCID
def fetch_orcid():
    r = requests.get(
        f"https://pub.orcid.org/v3.0/{ORCID_ID}/works",
        headers={"Accept": "application/json"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    pubs = []
    for group in r.json().get("group", []):
        s = (group.get("work-summary") or [{}])[0]
        title = ((s.get("title") or {}).get("title") or {}).get("value", "")
        year = to_int((((s.get("publication-date") or {}).get("year")) or {}).get("value"))
        venue = (s.get("journal-title") or {}).get("value", "") if s.get("journal-title") else ""
        doi = ""
        for ext in ((s.get("external-ids") or {}).get("external-id") or []):
            if ext.get("external-id-type") == "doi":
                doi = ext.get("external-id-value", "")
                break
        url = f"https://doi.org/{doi}" if doi else ((s.get("url") or {}) or {}).get("value", "")
        if title:
            pubs.append({
                "title": title.strip(), "authors": "", "venue": venue, "year": year,
                "citations": None, "url": url, "doi": doi,
            })
    return pubs


# ---------------------------------------------------------------- main
def main():
    old = json.loads(OUT.read_text()) if OUT.exists() else {"publications": []}
    pubs, profile, source = None, {}, None

    key = os.environ.get("SERPAPI_KEY", "").strip()
    if key:
        try:
            pubs, profile = fetch_scholar(key)
            source = "Google Scholar"
            print(f"Scholar: {len(pubs)} publications")
        except Exception as e:
            print(f"::warning::Scholar fetch failed: {e}")
    else:
        print("::warning::SERPAPI_KEY not set, skipping Scholar")

    orcid = None
    try:
        orcid = fetch_orcid()
        print(f"ORCID: {len(orcid)} works")
    except Exception as e:
        print(f"::warning::ORCID fetch failed: {e}")

    if pubs is None and orcid is not None:
        if old.get("source") == "Google Scholar" and len(orcid) <= len(old.get("publications", [])):
            print("::warning::Scholar unavailable; keeping the last Scholar data (richer than ORCID).")
            return
        pubs, source = orcid, "ORCID"
        profile = old.get("profile", {})  # keep last known Scholar metrics
    elif pubs is not None and orcid:
        by_title = {norm(p["title"]): p for p in orcid}
        for p in pubs:
            match = by_title.get(norm(p["title"]))
            if match and match["doi"]:
                p["doi"] = match["doi"]

    if not pubs:
        print("::error::No publication source succeeded; keeping existing data.")
        sys.exit(1)

    old_n = len(old.get("publications", []))
    if old_n and len(pubs) < 0.5 * old_n:
        print(f"::error::Got {len(pubs)} items vs {old_n} before; looks incomplete, not overwriting.")
        sys.exit(1)

    # de-duplicate by title, newest first
    seen, clean = set(), []
    for p in pubs:
        k = norm(p["title"])
        if k and k not in seen:
            seen.add(k)
            clean.append(p)
    clean.sort(key=lambda p: (-(p["year"] or 0), -(p["citations"] or 0)))

    new = {"source": source, "profile": profile, "publications": clean}
    if {k: old.get(k) for k in new} == new:
        print("No changes.")
        return

    new["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    OUT.write_text(json.dumps({"updated": new.pop("updated"), **new}, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(clean)} publications from {source}.")


if __name__ == "__main__":
    main()
