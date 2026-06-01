# VerifiedEarnings

A 100% **company-verified** earnings calendar — like an "earnings hub," but every
single date is backed by a primary source the company itself published. No
third-party aggregators, no analyst estimates, no guesses.

> If a company hasn't officially announced its next earnings date, we show **no
> date** instead of a fake one. That is the entire point.

## What makes it different

| | Typical earnings sites | VerifiedEarnings |
|---|---|---|
| Source of dates | Third-party aggregators, analyst estimates | The company's own SEC 8-K / IR page |
| Unannounced dates | Shown as an "estimated" date | Shown as **pending**, no date |
| Provenance | None | Exact quote + source URL on every entry |
| Re-checking | — | Automated re-verification pass |

## Sources we accept
- The company's **SEC EDGAR Form 8-K** (filed by the company itself).
- The company's **investor-relations** website.
- A **press release the company issued** over BusinessWire / GlobeNewswire / PR Newswire.

## Sources we reject
- Third-party earnings-calendar aggregators.
- Analyst / consensus estimates of an unannounced date.
- Brokerage "expected report" placeholders.

## Run it

```bash
cd verifiedearnings
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py            # http://localhost:8000
```

## The verification engine

`verifier.py` is the trust layer. It talks only to official SEC endpoints and to
the company IR URLs stored in `data/earnings.json`.

```bash
python verifier.py report        # print the calendar and every source
python verifier.py reverify      # re-fetch each source and confirm the date still matches
python verifier.py edgar AAPL    # list the recent 8-K filings Apple itself filed
```

How `reverify` works:
1. Resolve ticker → SEC CIK via the SEC's official `company_tickers.json`.
2. Pull the company's recent **Form 8-K** filings from `data.sec.gov`.
3. Scan each filing (and the IR page) for an earnings-announcement sentence and
   extract the date beside it.
4. Confirm it matches the stored date; record the quote, URL, and timestamp.
5. Flag anything that no longer matches for human review.

> SEC requires a descriptive User-Agent. Set one before running live:
> `export EDGAR_UA="VerifiedEarnings/1.0 (you@example.com)"`

## Data & API

- Dataset: [`data/earnings.json`](data/earnings.json) — every entry carries its
  source type, URL, verbatim quote, and retrieval date.
- JSON feed: `GET /api/earnings` and `GET /api/earnings/<TICKER>`.

## Project layout

```
verifiedearnings/
├── app.py                 # Flask web app (calendar, company pages, methodology, API)
├── verifier.py            # SEC-EDGAR + IR verification engine (CLI)
├── data/earnings.json     # verified + pending events, with full provenance
├── templates/             # base, index, company, methodology
├── static/style.css
└── requirements.txt
```

## Honesty note

The seed dataset was compiled on 2026-06-01 from each company's own
announcement. Dates can change; always confirm against the linked company source
before acting. Informational only — not investment advice.
