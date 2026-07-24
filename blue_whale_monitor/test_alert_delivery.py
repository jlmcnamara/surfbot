from __future__ import annotations

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from blue_whale_monitor.alert_delivery import alert_title, build_issue_body, decision_block
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
    def test_pre_return_title_signals_strength(self) -> None:
        item = sample_candidate(date(2026, 7, 24))
        self.assertEqual(
            alert_title([item], date(2026, 7, 24)),
            "🐋 STRONG BLUE-WHALE SIGNAL | Long Beach | Jul 24",
        )

    def test_post_return_title_is_direct_alert(self) -> None:
        item = sample_candidate(date(2026, 8, 6))
        self.assertEqual(
            alert_title([item], date(2026, 8, 6)),
            "🐋 BLUE WHALE ALERT | Long Beach | Aug 6",
        )


class AlertBodyTests(unittest.TestCase):
    def test_body_is_decision_oriented_and_deduplicatable(self) -> None:
        item = sample_candidate(date(2026, 8, 6))
        body = build_issue_body([item], date(2026, 8, 6))
        self.assertIn("# CHECK THE NEXT 72 HOURS", body)
        self.assertIn("Latest evidence", body)
        self.assertIn("Next action", body)
        self.assertIn("<!-- fingerprint:" + "a" * 64 + " -->", body)

    def test_family_timing_after_august_17(self) -> None:
        decision, explanation = decision_block(date(2026, 8, 17))
        self.assertEqual(decision, "CHECK A FAMILY DEPARTURE")
        self.assertIn("Corinna, Jax, and Quinn", explanation)


if __name__ == "__main__":
    unittest.main()
