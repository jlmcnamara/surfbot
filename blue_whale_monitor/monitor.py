#!/usr/bin/env python3
"""Zero-token Long Beach blue-whale sighting monitor.

The monitor checks official/operator sources plus tightly filtered public RSS
results. It posts to one persistent GitHub issue only when it finds a new,
recent, qualifying sighting. GitHub's normal issue notifications then deliver
email/push alerts without using a ChatGPT task slot or model tokens.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import quote_plus, urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup

PACIFIC = ZoneInfo("America/Los_Angeles")
TODAY = datetime.now(PACIFIC).date()
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "14"))
EARLY_ALERT_DATE = date.fromisoformat(os.getenv("EARLY_ALERT_DATE", "2026-08-04"))
FAMILY_ALERT_DATE = date.fromisoformat(os.getenv("FAMILY_ALERT_DATE", "2026-08-17"))
MONITOR_ISSUE_NUMBER = int(os.getenv("MONITOR_ISSUE_NUMBER", "3"))

HARBOR_BREEZE_URL = "https://harbor-cruises.com/harbor-cruises-sightings/"
INSTAGRAM_ACCOUNTS = ("harborbreezecruises", "aquariumpacific")
INSTAGRAM_API = "https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"

SEARCH_QUERY = (
    '"blue whale" ("Long Beach" OR "Harbor Breeze" OR '
    '"Aquarium of the Pacific" OR "Rainbow Harbor") California'
)
RSS_URLS = (
    "https://news.google.com/rss/search?q="
    + quote_plus(SEARCH_QUERY + " when:14d")
    + "&hl=en-US&gl=US&ceid=US:en",
    "https://www.bing.com/news/search?q="
    + quote_plus(SEARCH_QUERY)
    + "&format=rss",
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
INSTAGRAM_HEADERS = {
    **DEFAULT_HEADERS,
    "X-IG-App-ID": "936619743392459",
    "Accept": "*/*",
}

DATE_LINE_RE = re.compile(
    r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,?\s+"
    r"\d{1,2}$",
    re.IGNORECASE,
)
TIME_LINE_RE = re.compile(r"^\d{1,2}:\d{2}\s*(am|pm)$", re.IGNORECASE)
BLUE_WHALE_RE = re.compile(r"\bblue\s+whales?\b", re.IGNORECASE)
STRONG_PRESENCE_RE = re.compile(
    r"(?:\b(?:[2-9]|\d{2,})\s+blue\s+whales?\b|"
    r"\bmultiple\s+blue\s+whales?\b|"
    r"\bblue\s+whales?\s+(?:again|feeding|everywhere|all\s+around)\b|"
    r"\bsustained\b|\bunusually\s+strong\b)",
    re.IGNORECASE,
)
FINGERPRINT_RE = re.compile(r"<!--\s*fingerprint:([0-9a-f]{64})\s*-->")


@dataclass(frozen=True)
class Candidate:
    source: str
    source_url: str
    observed_at: datetime
    title: str
    details: str
    credibility: int
    fingerprint: str


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def make_fingerprint(*parts: str) -> str:
    payload = "|".join(normalize_space(part).lower() for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_recent(moment: datetime, today: date, days: int = LOOKBACK_DAYS) -> bool:
    local_date = moment.astimezone(PACIFIC).date()
    return today - timedelta(days=days) <= local_date <= today + timedelta(days=1)


def parse_yearless_date(value: str, today: date) -> date:
    cleaned = value.replace(",", "")
    parsed = datetime.strptime(cleaned, "%a %b %d").date().replace(year=today.year)
    # Sightings pages often omit the year. Choose the most recent plausible date.
    if parsed > today + timedelta(days=30):
        parsed = parsed.replace(year=today.year - 1)
    return parsed


def parse_harbor_breeze(html_text: str, today: date = TODAY) -> list[Candidate]:
    """Parse recent blue-whale rows from Harbor Breeze's sightings section."""
    soup = BeautifulSoup(html_text, "html.parser")
    page_text = soup.get_text("\n")
    marker = "Season Sightings Over The Last Year By Date"
    if marker not in page_text:
        return []

    section = page_text.split(marker, 1)[1]
    section = section.split("Have Questions?", 1)[0]
    lines = [normalize_space(line) for line in section.splitlines()]
    lines = [line for line in lines if line]

    candidates: list[Candidate] = []
    current_date: date | None = None

    for index, line in enumerate(lines):
        if DATE_LINE_RE.fullmatch(line):
            current_date = parse_yearless_date(line, today)
            continue

        if not TIME_LINE_RE.fullmatch(line) or current_date is None:
            continue
        if index + 1 >= len(lines):
            continue

        description = lines[index + 1]
        if not BLUE_WHALE_RE.search(description):
            continue

        parsed_time = datetime.strptime(line.replace(" ", ""), "%I:%M%p").time()
        observed = datetime.combine(current_date, parsed_time, PACIFIC)
        if not is_recent(observed, today):
            continue

        fingerprint = make_fingerprint(
            "harbor-breeze",
            current_date.isoformat(),
            line,
            description,
        )
        candidates.append(
            Candidate(
                source="Harbor Breeze official sightings",
                source_url=HARBOR_BREEZE_URL,
                observed_at=observed,
                title=f"{description} — {current_date:%b %-d} at {line}",
                details=description,
                credibility=3,
                fingerprint=fingerprint,
            )
        )

    return candidates


def parse_instagram_payload(
    payload: dict, username: str, today: date = TODAY
) -> list[Candidate]:
    """Extract recent blue-whale posts from an official Instagram payload."""
    edges = (
        payload.get("data", {})
        .get("user", {})
        .get("edge_owner_to_timeline_media", {})
        .get("edges", [])
    )
    candidates: list[Candidate] = []

    for edge in edges:
        node = edge.get("node", {})
        timestamp = node.get("taken_at_timestamp")
        shortcode = node.get("shortcode")
        captions = node.get("edge_media_to_caption", {}).get("edges", [])
        caption = ""
        if captions:
            caption = captions[0].get("node", {}).get("text", "")
        caption = normalize_space(caption)

        if not timestamp or not shortcode or not BLUE_WHALE_RE.search(caption):
            continue

        observed = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).astimezone(PACIFIC)
        if not is_recent(observed, today):
            continue

        post_url = f"https://www.instagram.com/p/{shortcode}/"
        title = caption[:180] + ("…" if len(caption) > 180 else "")
        candidates.append(
            Candidate(
                source=f"Official Instagram @{username}",
                source_url=post_url,
                observed_at=observed,
                title=title,
                details=caption[:800],
                credibility=3,
                fingerprint=make_fingerprint(username, shortcode, caption),
            )
        )

    return candidates


def entry_datetime(entry: object) -> datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc).astimezone(PACIFIC)

    published = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if published:
        try:
            value = parsedate_to_datetime(published)
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(PACIFIC)
        except (TypeError, ValueError, OverflowError):
            return None
    return None


def is_long_beach_relevant(text: str, url: str) -> bool:
    haystack = f"{text} {url}".lower()
    strong_terms = (
        "harbor breeze",
        "aquarium of the pacific",
        "rainbow harbor",
        "catalina channel",
        "san pedro channel",
        "2seewhales",
        "harbor-cruises.com",
        "visitlongbeach.com",
        "long beach, ca",
        "long beach california",
        "los angeles",
    )
    if any(term in haystack for term in strong_terms):
        return True

    if "long beach" not in haystack:
        return False
    excluded = ("long beach island", "long island", "new york", "montauk")
    return not any(term in haystack for term in excluded)


def source_credibility(url: str, source_name: str) -> int:
    host = urlparse(url).netloc.lower()
    combined = f"{host} {source_name}".lower()
    official = (
        "harbor-cruises.com",
        "2seewhales.com",
        "aquariumofpacific.org",
        "visitlongbeach.com",
        "harbor breeze",
        "aquarium of the pacific",
    )
    return 3 if any(term in combined for term in official) else 2


def parse_rss(xml_text: str, today: date = TODAY) -> list[Candidate]:
    feed = feedparser.parse(xml_text)
    candidates: list[Candidate] = []

    for entry in feed.entries:
        title = normalize_space(getattr(entry, "title", ""))
        summary_html = getattr(entry, "summary", "") or getattr(entry, "description", "")
        summary = normalize_space(BeautifulSoup(summary_html, "html.parser").get_text(" "))
        link = normalize_space(getattr(entry, "link", ""))
        source_obj = getattr(entry, "source", None)
        source_name = normalize_space(getattr(source_obj, "title", "")) if source_obj else ""
        combined = f"{title} {summary} {source_name}"

        if not BLUE_WHALE_RE.search(combined):
            continue
        if not is_long_beach_relevant(combined, link):
            continue

        observed = entry_datetime(entry)
        if observed is None or not is_recent(observed, today):
            continue

        candidates.append(
            Candidate(
                source=source_name or "Recent web/news result",
                source_url=link,
                observed_at=observed,
                title=title,
                details=summary[:800],
                credibility=source_credibility(link, source_name),
                fingerprint=make_fingerprint(
                    source_name,
                    observed.date().isoformat(),
                    title,
                    link,
                ),
            )
        )

    return candidates


def deduplicate(candidates: Iterable[Candidate]) -> list[Candidate]:
    by_fingerprint: dict[str, Candidate] = {}
    title_keys: set[str] = set()

    for candidate in sorted(candidates, key=lambda item: item.observed_at, reverse=True):
        title_key = normalize_space(candidate.title).lower()
        if candidate.fingerprint in by_fingerprint or title_key in title_keys:
            continue
        by_fingerprint[candidate.fingerprint] = candidate
        title_keys.add(title_key)

    return list(by_fingerprint.values())


def select_alert_candidates(
    candidates: Iterable[Candidate], today: date = TODAY
) -> list[Candidate]:
    recent = [candidate for candidate in deduplicate(candidates) if candidate.credibility >= 2]
    if today >= EARLY_ALERT_DATE:
        return recent

    # Before John returns on August 4, suppress isolated single sightings. Alert
    # only for clear strength language or corroborated/repeated recent evidence.
    strong = [
        candidate
        for candidate in recent
        if candidate.credibility >= 3
        and STRONG_PRESENCE_RE.search(f"{candidate.title} {candidate.details}")
    ]
    if strong:
        return strong

    distinct_sources = {candidate.source for candidate in recent}
    distinct_dates = {candidate.observed_at.date() for candidate in recent}
    if len(recent) >= 2 and (len(distinct_sources) >= 2 or len(distinct_dates) >= 2):
        return recent

    return []


def request_json(url: str, token: str) -> object:
    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **DEFAULT_HEADERS,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def existing_fingerprints(repo: str, issue_number: int, token: str) -> set[str]:
    fingerprints: set[str] = set()
    page = 1
    while True:
        comments = request_json(
            f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
            f"?per_page=100&page={page}",
            token,
        )
        if not isinstance(comments, list) or not comments:
            break
        for comment in comments:
            fingerprints.update(FINGERPRINT_RE.findall(comment.get("body", "")))
        if len(comments) < 100:
            break
        page += 1
    return fingerprints


def build_comment(candidates: list[Candidate], today: date = TODAY) -> str:
    lines = [f"## Blue-whale alert — {today:%B %-d, %Y}", ""]
    lines.append("New qualifying Long Beach blue-whale evidence was detected:")
    lines.append("")

    for candidate in candidates:
        observed = candidate.observed_at.astimezone(PACIFIC)
        lines.extend(
            [
                f"- **{candidate.source} — {observed:%B %-d, %Y at %-I:%M %p PT}**",
                f"  - {candidate.title}",
                f"  - [Open source]({candidate.source_url})",
                f"  <!-- fingerprint:{candidate.fingerprint} -->",
            ]
        )

    lines.append("")
    if today < EARLY_ALERT_DATE:
        lines.append(
            "**Timing:** This met the stricter pre–August 4 threshold for sustained "
            "or unusually strong presence. Continue monitoring rather than booking from "
            "Germany unless the pattern persists into your return window."
        )
    elif today < FAMILY_ALERT_DATE:
        lines.append(
            "**Timing:** You are back in Los Angeles. This is relevant for a near-term "
            "Long Beach departure; check the next few Harbor Breeze sailings."
        )
    else:
        lines.append(
            "**Family timing:** Corinna, Jax, and Quinn are back. This is relevant for "
            "the stadium-seating Harbor Breeze/Aquarium family outing."
        )

    lines.append("")
    lines.append(
        "This monitor checks every six hours and stays active after alerts. Sightings "
        "remain wildlife-dependent and are never guaranteed."
    )
    return "\n".join(lines)


def post_issue_comment(repo: str, issue_number: int, token: str, body: str) -> None:
    response = requests.post(
        f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **DEFAULT_HEADERS,
        },
        json={"body": body},
        timeout=30,
    )
    response.raise_for_status()


def collect_candidates(today: date = TODAY) -> tuple[list[Candidate], list[str]]:
    candidates: list[Candidate] = []
    successes: list[str] = []

    try:
        response = requests.get(HARBOR_BREEZE_URL, headers=DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
        candidates.extend(parse_harbor_breeze(response.text, today))
        successes.append("Harbor Breeze sightings page")
    except requests.RequestException as exc:
        print(f"Harbor Breeze fetch failed: {exc}", file=sys.stderr)

    for username in INSTAGRAM_ACCOUNTS:
        try:
            response = requests.get(
                INSTAGRAM_API.format(username=username),
                headers=INSTAGRAM_HEADERS,
                timeout=30,
            )
            response.raise_for_status()
            candidates.extend(parse_instagram_payload(response.json(), username, today))
            successes.append(f"Instagram @{username}")
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            # Instagram often rate-limits unauthenticated access. It is a useful
            # source when available, but never a single point of failure.
            print(f"Instagram @{username} unavailable: {exc}", file=sys.stderr)

    for rss_url in RSS_URLS:
        try:
            response = requests.get(rss_url, headers=DEFAULT_HEADERS, timeout=30)
            response.raise_for_status()
            candidates.extend(parse_rss(response.text, today))
            successes.append(urlparse(rss_url).netloc)
        except requests.RequestException as exc:
            print(f"RSS fetch failed for {rss_url}: {exc}", file=sys.stderr)

    return deduplicate(candidates), successes


def main() -> int:
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    dry_run = "--dry-run" in sys.argv

    candidates, successes = collect_candidates(TODAY)
    if not successes:
        raise RuntimeError("All monitoring sources failed; refusing to report a clean run.")

    selected = select_alert_candidates(candidates, TODAY)
    print(
        f"Checked {len(successes)} source endpoints; found {len(candidates)} recent "
        f"candidate(s), {len(selected)} meeting today's alert threshold."
    )

    if dry_run:
        for candidate in selected:
            print(f"DRY RUN: {candidate.source}: {candidate.title}")
        return 0

    if not repo or not token:
        raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN are required outside dry-run mode.")

    seen = existing_fingerprints(repo, MONITOR_ISSUE_NUMBER, token)
    new_candidates = [candidate for candidate in selected if candidate.fingerprint not in seen]
    if not new_candidates:
        print("No new qualifying sighting; no notification sent.")
        return 0

    post_issue_comment(
        repo,
        MONITOR_ISSUE_NUMBER,
        token,
        build_comment(new_candidates, TODAY),
    )
    print(f"Posted alert with {len(new_candidates)} new sighting(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
