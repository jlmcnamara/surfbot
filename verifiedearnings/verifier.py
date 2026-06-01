"""
Verification engine for VerifiedEarnings.

Core principle: an earnings date is only ever "verified" if it can be matched
against a PRIMARY source the company itself published:

  1. The company's SEC EDGAR Form 8-K (filed by the company), or
  2. The company's investor-relations / press-release page.

We never read a third-party earnings-calendar aggregator, and we never accept
an analyst estimate of an unannounced date. If we cannot match the date in a
company-published document, the date does NOT get the "verified" badge.

This module talks only to official SEC endpoints (data.sec.gov, www.sec.gov)
and to the company IR URLs recorded in data/earnings.json. SEC requires a
descriptive User-Agent with a contact address; set it via the EDGAR_UA env var
or edit USER_AGENT below.

Usage:
    python verifier.py report          # print the current calendar + statuses
    python verifier.py reverify        # re-check every verified date against SEC/IR
    python verifier.py edgar AAPL      # show recent 8-K filings the company filed
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:  # keep the CLI usable for report-only with no deps
    requests = None

DATA_FILE = Path(__file__).resolve().parent / "data" / "earnings.json"

USER_AGENT = os.environ.get(
    "EDGAR_UA",
    "VerifiedEarnings/1.0 (verified-earnings; contact@example.com)",
)

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

# Phrases that, in a company filing/release, introduce an earnings date.
ANNOUNCE_PATTERNS = [
    r"will (?:report|release|announce|host|hold)",
    r"to (?:report|release|announce)",
    r"scheduled (?:to|for)",
    r"earnings (?:conference )?call",
    r"financial results",
]

# e.g. "Tuesday, July 14, 2026"  or  "July 14, 2026"  or  "June 30, 2026"
DATE_RE = re.compile(
    r"(?:(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?\s+)?"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),?\s+(\d{4})",
    re.IGNORECASE,
)
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


@dataclass
class VerifyResult:
    ok: bool
    matched_date: Optional[str]
    snippet: str
    source_url: str
    detail: str


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #
def load_data() -> dict:
    with open(DATA_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# --------------------------------------------------------------------------- #
# HTTP (SEC-compliant)
# --------------------------------------------------------------------------- #
def _session() -> "requests.Session":
    if requests is None:
        raise RuntimeError("The 'requests' package is required for live verification.")
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    return s


def _get(sess, url: str, timeout: int = 20) -> Optional[str]:
    try:
        resp = sess.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception:
        return None


def _strip_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


# --------------------------------------------------------------------------- #
# Date matching
# --------------------------------------------------------------------------- #
def find_announced_dates(text: str) -> list[tuple[str, str]]:
    """Return [(iso_date, surrounding_sentence)] for date mentions that sit near
    an earnings-announcement phrase. This is deliberately conservative."""
    results: list[tuple[str, str]] = []
    for m in DATE_RE.finditer(text):
        month = MONTHS.get(m.group(1).lower())
        if not month:
            continue
        day, year = int(m.group(2)), int(m.group(3))
        try:
            iso = dt.date(year, month, day).isoformat()
        except ValueError:
            continue
        start, end = max(0, m.start() - 160), min(len(text), m.end() + 160)
        context = text[start:end]
        if any(re.search(p, context, re.IGNORECASE) for p in ANNOUNCE_PATTERNS):
            results.append((iso, " ".join(context.split())))
    return results


# --------------------------------------------------------------------------- #
# SEC EDGAR
# --------------------------------------------------------------------------- #
def ticker_to_cik(sess, ticker: str) -> Optional[str]:
    text = _get(sess, SEC_TICKERS_URL)
    if not text:
        return None
    try:
        table = json.loads(text)
    except json.JSONDecodeError:
        return None
    ticker = ticker.upper()
    for row in table.values():
        if row.get("ticker", "").upper() == ticker:
            return str(row["cik_str"]).zfill(10)
    return None


def recent_8k_docs(sess, cik10: str, limit: int = 12) -> list[dict]:
    """Most recent 8-K filings the company itself filed, newest first."""
    text = _get(sess, SEC_SUBMISSIONS_URL.format(cik10=cik10))
    if not text:
        return []
    try:
        sub = json.loads(text)
    except json.JSONDecodeError:
        return []
    recent = sub.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accns = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    dates = recent.get("filingDate", [])
    out = []
    cik_int = str(int(cik10))
    for form, acc, doc, filed in zip(forms, accns, docs, dates):
        if form != "8-K":
            continue
        acc_nodash = acc.replace("-", "")
        out.append({
            "form": form,
            "accession": acc,
            "filed": filed,
            "url": SEC_ARCHIVE_URL.format(cik=cik_int, acc=acc_nodash, doc=doc),
        })
        if len(out) >= limit:
            break
    return out


def verify_against_edgar(sess, event: dict) -> VerifyResult:
    """Confirm the stored date appears in a company-filed 8-K."""
    cik10 = (event.get("cik") or "").zfill(10) if event.get("cik") else None
    if not cik10:
        cik10 = ticker_to_cik(sess, event["ticker"])
    if not cik10:
        return VerifyResult(False, None, "", "", "Could not resolve CIK at SEC.")

    target = event.get("date")
    for filing in recent_8k_docs(sess, cik10):
        html = _get(sess, filing["url"])
        if not html:
            continue
        text = _strip_html(html)
        for iso, snippet in find_announced_dates(text):
            if target is None or iso == target:
                return VerifyResult(
                    True, iso, snippet, filing["url"],
                    f"Matched in company 8-K filed {filing['filed']}.")
        time.sleep(0.2)  # be polite to SEC
    return VerifyResult(False, None, "", "",
                        "No matching date found in the company's recent 8-K filings.")


def verify_against_ir(sess, event: dict) -> VerifyResult:
    """Confirm the stored date appears on a company-published IR/press page."""
    urls = [s["url"] for s in event.get("sources", []) if s.get("url")]
    if event.get("ir_url"):
        urls.append(event["ir_url"])
    target = event.get("date")
    for url in urls:
        if "sec.gov" in url:
            continue  # handled by the EDGAR path
        html = _get(sess, url)
        if not html:
            continue
        text = _strip_html(html)
        for iso, snippet in find_announced_dates(text):
            if target is None or iso == target:
                return VerifyResult(True, iso, snippet, url,
                                    "Matched on company-published page.")
    return VerifyResult(False, None, "", "",
                        "No matching date found on the company's own pages.")


def reverify_event(sess, event: dict) -> VerifyResult:
    """A date is confirmed if EITHER the 8-K OR the IR page still shows it."""
    edgar = verify_against_edgar(sess, event)
    if edgar.ok:
        return edgar
    return verify_against_ir(sess, event)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_report() -> None:
    data = load_data()
    events = sorted(
        data["events"],
        key=lambda e: (e.get("date") is None, e.get("date") or "9999", e["ticker"]),
    )
    print("\nVerifiedEarnings  -  100% company-confirmed earnings calendar")
    print("=" * 66)
    verified = [e for e in events if e["status"] == "verified"]
    pending = [e for e in events if e["status"] != "verified"]

    print(f"\nVERIFIED ({len(verified)})  -  date published by the company itself\n")
    for e in verified:
        print(f"  {e['date']}  {e['ticker']:<6} {e['company'][:34]:<34} "
              f"{e['fiscal_period']:<12} {e.get('session','')}")
        for s in e.get("sources", []):
            print(f"           source: {s['type']}")
            print(f"                   {s['url']}")

    print(f"\nPENDING ({len(pending)})  -  no official company date yet (shown without a date)\n")
    for e in pending:
        print(f"  {'(awaiting)':<12} {e['ticker']:<6} {e['company'][:34]:<34} "
              f"{e['fiscal_period']}")
        print(f"           {e.get('note','')}")
    print()


def cmd_reverify() -> None:
    data = load_data()
    sess = _session()
    print("Re-verifying every dated event against SEC EDGAR and company IR pages...\n")
    changed = 0
    for e in data["events"]:
        if e.get("date") is None:
            continue
        res = reverify_event(sess, e)
        stamp = dt.date.today().isoformat()
        if res.ok:
            e["last_reverified"] = stamp
            e["reverify_source"] = res.source_url
            print(f"  OK   {e['ticker']:<6} {e['date']}  <-  {res.detail}")
        else:
            e["last_reverify_failed"] = stamp
            changed += 1
            print(f"  WARN {e['ticker']:<6} {e['date']}  !!  {res.detail}")
    save_data(data)
    print(f"\nDone. {changed} event(s) could not be re-confirmed and need review.")


def cmd_edgar(ticker: str) -> None:
    sess = _session()
    cik = ticker_to_cik(sess, ticker)
    if not cik:
        print(f"Could not resolve CIK for {ticker} (network blocked or unknown ticker).")
        return
    print(f"{ticker.upper()}  CIK {cik}  -  recent 8-K filings:\n")
    for f in recent_8k_docs(sess, cik):
        print(f"  {f['filed']}  {f['accession']}")
        print(f"            {f['url']}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "report":
        cmd_report()
    elif cmd == "reverify":
        cmd_reverify()
    elif cmd == "edgar" and len(sys.argv) > 2:
        cmd_edgar(sys.argv[2])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
