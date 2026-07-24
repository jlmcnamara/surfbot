from __future__ import annotations

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from blue_whale_monitor.alert_delivery import (
    alert_title,
    build_issue_body,
    evidence_sentence,
    recommendation,
)
from blue_whale_monitor.monitor import Candidate

PACIFIC = ZoneInfo("America/Los_Angeles")


def sample_candidate(observed: date, details: str = "2 Blue Whales feeding") -> Candidate:
    return Candidate(
        source="Harbor Breeze official sightings",
        source_url="https://harbor-cruises.com/harbor-cruises-sightings/",
        observed_at=datetime(observed.year, observed.month, observed.day, 15, 0, tzinfo=PACIFIC),
        title=details,
        details=details,
        credibility=3,
        fingerprint="a" * 64,
    )


class AlertTitleTests(unittest.TestCase):
    def test_title_is_plain_and_specific(self) -> None:
        item = sample_candidate(date(2026, 8, 6))
        self.assertEqual(
            alert_title([item], date(2026, 8, 6)),
            "Blue whale near Long Beach — Aug 6",
        )


class AlertBodyTests(unittest.TestCase):
    def test_body_is_short_and_deduplicatable(self) -> None:
        item = sample_candidate(date(2026, 8, 6))
        body = build_issue_body([item], date(2026, 8, 6))
        self.assertIn(
            "Harbor Breeze official sightings reported 2 Blue Whales feeding on Thu, Aug 6 at 3:00 PM PT.",
            body,
        )
        self.assertIn("Recommendation: Check Long Beach departures in the next 72 hours.", body)
        self.assertIn("[View source]", body)
        self.assertIn("<!-- fingerprint:" + "a" * 64 + " -->", body)
        self.assertNotIn("Latest evidence", body)
        self.assertNotIn("Next action", body)
        self.assertNotIn("🐋", body)

    def test_pre_return_recommendation(self) -> None:
        self.assertEqual(
            recommendation(date(2026, 7, 24)),
            "Keep watching. You return August 4.",
        )

    def test_family_recommendation_after_august_17(self) -> None:
        self.assertEqual(
            recommendation(date(2026, 8, 17)),
            "Check a family departure in the next 72 hours.",
        )

    def test_evidence_sentence_ends_once(self) -> None:
        item = sample_candidate(date(2026, 8, 6), "Blue whale seen.")
        self.assertEqual(
            evidence_sentence(item),
            "Harbor Breeze official sightings reported Blue whale seen on Thu, Aug 6 at 3:00 PM PT.",
        )


if __name__ == "__main__":
    unittest.main()
