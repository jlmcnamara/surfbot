from __future__ import annotations

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from blue_whale_monitor.monitor import (
    Candidate,
    is_long_beach_relevant,
    parse_harbor_breeze,
    parse_instagram_payload,
    select_alert_candidates,
)

PACIFIC = ZoneInfo("America/Los_Angeles")


def candidate(details: str, observed: date, source: str = "Official source") -> Candidate:
    return Candidate(
        source=source,
        source_url="https://example.com/sighting",
        observed_at=datetime(observed.year, observed.month, observed.day, 12, tzinfo=PACIFIC),
        title=details,
        details=details,
        credibility=3,
        fingerprint=(details.encode("utf-8").hex() + "0" * 64)[:64],
    )


class HarborBreezeParserTests(unittest.TestCase):
    def test_parses_recent_blue_whale_row(self) -> None:
        html = """
        <html><body>
        <h3>Season Sightings Over The Last Year By Date</h3>
        <div>Triumphant</div><div>Fri Jul, 24</div><div>3:00pm</div>
        <div>2 Blue Whales, 500 Common Dolphins</div>
        <h3>Have Questions?</h3>
        </body></html>
        """
        results = parse_harbor_breeze(html, date(2026, 7, 24))
        self.assertEqual(len(results), 1)
        self.assertIn("2 Blue Whales", results[0].title)
        self.assertEqual(results[0].observed_at.date(), date(2026, 7, 24))

    def test_filters_stale_yearless_rows(self) -> None:
        html = """
        <html><body>
        <h3>Season Sightings Over The Last Year By Date</h3>
        <div>Triumphant</div><div>Sun Sep, 22</div><div>4:30pm</div>
        <div>3 Blue Whales</div>
        <h3>Have Questions?</h3>
        </body></html>
        """
        results = parse_harbor_breeze(html, date(2026, 7, 24))
        self.assertEqual(results, [])


class InstagramParserTests(unittest.TestCase):
    def test_parses_recent_official_post(self) -> None:
        timestamp = int(datetime(2026, 7, 23, 12, tzinfo=PACIFIC).timestamp())
        payload = {
            "data": {
                "user": {
                    "edge_owner_to_timeline_media": {
                        "edges": [
                            {
                                "node": {
                                    "taken_at_timestamp": timestamp,
                                    "shortcode": "ABC123",
                                    "edge_media_to_caption": {
                                        "edges": [
                                            {
                                                "node": {
                                                    "text": "Two blue whales feeding off Long Beach today."
                                                }
                                            }
                                        ]
                                    },
                                }
                            }
                        ]
                    }
                }
            }
        }
        results = parse_instagram_payload(payload, "harborbreezecruises", date(2026, 7, 24))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].credibility, 3)
        self.assertIn("ABC123", results[0].source_url)


class AlertThresholdTests(unittest.TestCase):
    def test_suppresses_single_sighting_before_return(self) -> None:
        item = candidate("One blue whale seen today", date(2026, 7, 24))
        self.assertEqual(select_alert_candidates([item], date(2026, 7, 24)), [])

    def test_allows_strong_presence_before_return(self) -> None:
        item = candidate("4 blue whales feeding today", date(2026, 7, 24))
        self.assertEqual(select_alert_candidates([item], date(2026, 7, 24)), [item])

    def test_allows_credible_recent_sighting_after_return(self) -> None:
        item = candidate("One blue whale seen today", date(2026, 8, 4))
        self.assertEqual(select_alert_candidates([item], date(2026, 8, 4)), [item])


class RelevanceTests(unittest.TestCase):
    def test_rejects_new_york_long_beach(self) -> None:
        self.assertFalse(
            is_long_beach_relevant(
                "Blue whale near Long Beach Island, New York",
                "https://example.com/new-york",
            )
        )

    def test_accepts_operator_reference(self) -> None:
        self.assertTrue(
            is_long_beach_relevant(
                "Blue whale spotted by Harbor Breeze",
                "https://example.com/post",
            )
        )


if __name__ == "__main__":
    unittest.main()
