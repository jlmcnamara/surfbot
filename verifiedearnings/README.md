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

## Deployment

The app is a stateless Flask service that serves a JSON dataset, so it runs on
anything that can run a Python web process. Production uses **gunicorn**, not the
Flask dev server.

**Run it like production locally:**
```bash
gunicorn app:app --bind 0.0.0.0:8000 --workers 2
```

**Docker (works on Render, Railway, Fly.io, Cloud Run, ECS, a VPS):**
```bash
docker build -t verifiedearnings verifiedearnings/
docker run -p 8000:8000 verifiedearnings
```
The image runs gunicorn and honours an injected `$PORT`.

**Platform-as-a-service:** a `Procfile` is included, so Render / Railway / Heroku
detect the web process automatically — point the platform at the `verifiedearnings/`
directory and it builds from `requirements.txt`.

**Static option:** because there's no database and no user input, you can also
front it with a CDN and cache aggressively, or pre-render the pages — every
response is deterministic from `data/earnings.json`.

### Keeping the data fresh (the important part)

The dataset is the product, so it has to stay honest after deploy:

- **Re-verification** — `.github/workflows/refresh-earnings.yml` runs
  `python verifier.py reverify` on a weekday schedule. It re-fetches every source
  from SEC EDGAR + the company IR pages, commits any drift (e.g. a moved date), and
  flags sources that no longer match. GitHub runners have the outbound internet the
  dev sandbox lacks. Redeploy on push (most PaaS platforms do this automatically),
  or run the container with a small sidecar that pulls the latest data.
- **Adding companies / new announcements** — `reverify` confirms dates that are
  already in the file; it does not yet discover brand-new announcements on its own.
  New entries are added to `data/earnings.json` (each with its primary source) and
  picked up on the next deploy. Automating discovery via EDGAR full-text search is
  the natural next step.

> SEC asks for a descriptive User-Agent. Set `EDGAR_UA="VerifiedEarnings/1.0
> (you@example.com)"` in your deploy environment and in the GitHub Action.

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
