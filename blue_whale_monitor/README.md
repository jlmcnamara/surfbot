# Long Beach blue-whale monitor

A lightweight, zero-token replacement for the ChatGPT blue-whale monitoring task.

## What it does

- Runs on GitHub Actions every six hours.
- Checks Harbor Breeze's official sightings page.
- Checks recent official Harbor Breeze and Aquarium of the Pacific Instagram posts when Instagram's public endpoint is available.
- Checks narrowly filtered recent Google News and Bing News RSS results.
- Creates a **new assigned GitHub issue for each qualifying alert**, producing a distinct email subject such as `🐋 BLUE WHALE ALERT | Long Beach | Aug 6`.
- Labels alert issues `blue-whale-alert` and embeds fingerprints to prevent duplicates.
- Keeps running after an alert.

GitHub's existing issue-notification emails deliver the alert to John's Gmail. No paid monitoring service, external API key, ChatGPT task slot, or model token is required.

## Alert format

Each alert starts with one decision:

- `KEEP WATCHING` before August 4, when John is still in Germany.
- `CHECK THE NEXT 72 HOURS` from August 4 through August 16.
- `CHECK A FAMILY DEPARTURE` from August 17 onward.

The email then shows the latest evidence, source links, and the immediate booking-check action. Routine workflow success messages are not sent as sighting alerts.

## Timing logic

- Before August 4, 2026: suppress isolated sightings; alert only for sustained, corroborated, or unusually strong blue-whale presence.
- August 4–16, 2026: alert for any new credible recent sighting relevant to a near-term Long Beach departure.
- August 17 onward: frame the alert for the Harbor Breeze/Aquarium family outing with Corinna, Jax, and Quinn.

## Manual test

```bash
python -m pip install -r blue_whale_monitor/requirements.txt
python -m unittest discover -s blue_whale_monitor -p "test_*.py"
python -m blue_whale_monitor.alert_delivery --dry-run
```

The live GitHub run receives `GITHUB_TOKEN` automatically and creates an assigned, labeled alert issue only when a new sighting qualifies.
