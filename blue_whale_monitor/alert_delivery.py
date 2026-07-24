#!/usr/bin/env python3
"""Deliver blue-whale sightings as distinct, decision-oriented GitHub alerts.

Each qualifying sighting creates a new GitHub issue whose title becomes an
immediately recognizable email subject. The issue is created silently, then a
single mention comment triggers one useful email. Prior alerts are scanned for
hidden fingerprints, so the same sighting is never sent twice.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from typing import Iterable

import requests

from blue_whale_monitor.monitor import (
    DEFAULT_HEADERS,
    EARLY_ALERT_DATE,
    FAMILY_ALERT_DATE,
    FINGERPRINT_RE,
    HARBOR_BREEZE_URL,
    PACIFIC,
    TODAY,
    Candidate,
    collect_candidates,
    select_alert_candidates,
)

ALERT_LABEL = "blue-whale-alert"
ALERT_LABEL_COLOR = "0e8a16"
ALERT_OWNER = os.getenv("ALERT_OWNER", "jlmcnamara")
AQUARIUM_WHALE_WATCH_URL = (
    "https://www.aquariumofpacific.org/education/info/whale_watch"
)


def github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        **DEFAULT_HEADERS,
    }


def existing_fingerprints(repo: str, token: str) -> set[str]:
    """Read fingerprints from all prior alert-issue bodies."""
    fingerprints: set[str] = set()
    page = 1

    while True:
        response = requests.get(
            f"https://api.github.com/repos/{repo}/issues",
            headers=github_headers(token),
            params={
                "state": "all",
                "labels": ALERT_LABEL,
                "per_page": 100,
                "page": page,
            },
            timeout=30,
        )
        response.raise_for_status()
        issues = response.json()
        if not isinstance(issues, list) or not issues:
            break

        for issue in issues:
            fingerprints.update(FINGERPRINT_RE.findall(issue.get("body") or ""))

        if len(issues) < 100:
            break
        page += 1

    return fingerprints


def alert_title(candidates: Iterable[Candidate], today: date = TODAY) -> str:
    latest = max(candidate.observed_at.astimezone(PACIFIC) for candidate in candidates)
    prefix = "🐋 STRONG BLUE-WHALE SIGNAL" if today < EARLY_ALERT_DATE else "🐋 BLUE WHALE ALERT"
    return f"{prefix} | Long Beach | {latest:%b %-d}"


def decision_block(today: date) -> tuple[str, str]:
    if today < EARLY_ALERT_DATE:
        return (
            "KEEP WATCHING",
            "This cleared the stricter pre–August 4 threshold. Do not book from Germany yet; watch whether the pattern persists into your return window.",
        )
    if today < FAMILY_ALERT_DATE:
        return (
            "CHECK THE NEXT 72 HOURS",
            "You are back in Los Angeles. Review the next few Long Beach stadium-seat departures while the sighting is still current.",
        )
    return (
        "CHECK A FAMILY DEPARTURE",
        "Corinna, Jax, and Quinn are back. Review a Harbor Breeze/Aquarium departure for the family while the sighting is current.",
    )


def build_issue_body(candidates: list[Candidate], today: date = TODAY) -> str:
    decision, explanation = decision_block(today)
    lines = [
        f"# {decision}",
        "",
        explanation,
        "",
        "## Latest evidence",
        "",
    ]

    for candidate in sorted(candidates, key=lambda item: item.observed_at, reverse=True):
        observed = candidate.observed_at.astimezone(PACIFIC)
        lines.extend(
            [
                f"**{observed:%a, %b %-d at %-I:%M %p PT} — {candidate.source}**",
                "",
                candidate.title,
                "",
                f"[Open source]({candidate.source_url})",
                f"<!-- fingerprint:{candidate.fingerprint} -->",
                "",
            ]
        )

    lines.extend(
        [
            "## Next action",
            "",
            f"- [Check Harbor Breeze sightings]({HARBOR_BREEZE_URL})",
            f"- [Check Aquarium/Harbor Breeze whale-watch information]({AQUARIUM_WHALE_WATCH_URL})",
            "",
            "**Signal rule:** this is a new qualifying sighting, not a routine system-health message. The six-hour monitor remains active after every alert.",
            "",
            "Wildlife sightings are never guaranteed.",
        ]
    )
    return "\n".join(lines)


def ensure_label(repo: str, token: str) -> None:
    response = requests.get(
        f"https://api.github.com/repos/{repo}/labels/{ALERT_LABEL}",
        headers=github_headers(token),
        timeout=30,
    )
    if response.status_code == 200:
        return
    if response.status_code != 404:
        response.raise_for_status()

    create = requests.post(
        f"https://api.github.com/repos/{repo}/labels",
        headers=github_headers(token),
        json={
            "name": ALERT_LABEL,
            "color": ALERT_LABEL_COLOR,
            "description": "New qualifying Long Beach blue-whale sighting",
        },
        timeout=30,
    )
    if create.status_code not in (201, 422):
        create.raise_for_status()


def create_alert_issue(
    repo: str,
    token: str,
    candidates: list[Candidate],
    today: date = TODAY,
) -> str:
    ensure_label(repo, token)
    response = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers=github_headers(token),
        json={
            "title": alert_title(candidates, today),
            "body": build_issue_body(candidates, today),
            "labels": [ALERT_LABEL],
        },
        timeout=30,
    )
    response.raise_for_status()
    issue = response.json()

    notify = requests.post(
        f"https://api.github.com/repos/{repo}/issues/{issue['number']}/comments",
        headers=github_headers(token),
        json={"body": f"@{ALERT_OWNER}"},
        timeout=30,
    )
    notify.raise_for_status()
    return issue["html_url"]


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
        if selected:
            print(alert_title(selected, TODAY))
            print(build_issue_body(selected, TODAY))
        else:
            print("No qualifying sighting; no alert would be created.")
        return 0

    if not repo or not token:
        raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN are required outside dry-run mode.")

    seen = existing_fingerprints(repo, token)
    new_candidates = [candidate for candidate in selected if candidate.fingerprint not in seen]
    if not new_candidates:
        print("No new qualifying sighting; no notification sent.")
        return 0

    issue_url = create_alert_issue(repo, token, new_candidates, TODAY)
    print(f"Created one alert issue for {len(new_candidates)} new sighting(s): {issue_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
