"""
VerifiedEarnings - a 100% company-verified earnings calendar.

Unlike third-party "earnings hub" sites, every date here is backed by a
primary source the company itself published (an SEC 8-K it filed, or its own
investor-relations page). No analyst estimates, no aggregator guesses. If a
company has not officially announced, we show it as "pending" with no date.

Run:
    pip install -r requirements.txt
    python app.py            # http://localhost:8000
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

from flask import Flask, abort, jsonify, render_template

BASE = Path(__file__).resolve().parent
DATA_FILE = BASE / "data" / "earnings.json"

app = Flask(__name__)


def load_data() -> dict:
    with open(DATA_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def enrich(event: dict) -> dict:
    e = dict(event)
    d = parse_date(e.get("date"))
    e["_date"] = d
    if d:
        e["date_display"] = d.strftime("%a, %b %-d, %Y")
        e["weekday"] = d.strftime("%A")
        e["month_key"] = d.strftime("%Y-%m")
        e["month_display"] = d.strftime("%B %Y")
        e["days_away"] = (d - dt.date.today()).days
    return e


def get_events() -> list[dict]:
    data = load_data()
    return [enrich(e) for e in data["events"]]


def sort_key(e: dict):
    return (e["_date"] is None, e["_date"] or dt.date.max, e["ticker"])


@app.route("/")
def index():
    events = sorted(get_events(), key=sort_key)
    today = dt.date.today()

    verified = [e for e in events if e["status"] == "verified"]
    pending = [e for e in events if e["status"] != "verified"]
    upcoming = [e for e in verified if e["_date"] and e["_date"] >= today]

    # Group upcoming verified events by month for the calendar view.
    by_month: dict[str, list[dict]] = defaultdict(list)
    for e in upcoming:
        by_month[e["month_display"]].append(e)
    months = [{"name": name, "events": evs} for name, evs in by_month.items()]

    stats = {
        "verified": len(verified),
        "upcoming": len(upcoming),
        "pending": len(pending),
        "companies": len({e["ticker"] for e in events}),
    }
    meta = load_data()["meta"]
    return render_template(
        "index.html",
        months=months,
        pending=pending,
        stats=stats,
        meta=meta,
        today=today.strftime("%A, %B %-d, %Y"),
    )


@app.route("/methodology")
def methodology():
    meta = load_data()["meta"]
    return render_template("methodology.html", meta=meta)


@app.route("/company/<ticker>")
def company(ticker: str):
    ticker = ticker.upper()
    events = sorted(
        [e for e in get_events() if e["ticker"] == ticker], key=sort_key
    )
    if not events:
        abort(404)
    return render_template("company.html", ticker=ticker, events=events,
                           company_name=events[0]["company"])


@app.route("/api/earnings")
def api_earnings():
    """Public JSON feed. Each item carries its primary-source provenance."""
    data = load_data()
    return jsonify({
        "policy": data["meta"]["policy"],
        "generated": data["meta"]["generated"],
        "events": data["events"],
    })


@app.route("/api/earnings/<ticker>")
def api_company(ticker: str):
    ticker = ticker.upper()
    data = load_data()
    events = [e for e in data["events"] if e["ticker"].upper() == ticker]
    if not events:
        abort(404)
    return jsonify({"ticker": ticker, "events": events})


@app.template_filter("badge")
def badge(status: str) -> str:
    return "verified" if status == "verified" else "pending"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
