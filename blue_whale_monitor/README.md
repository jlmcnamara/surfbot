# Long Beach blue-whale monitor

A lightweight, zero-token replacement for the ChatGPT blue-whale monitoring task.

## What it does

- Runs on GitHub Actions every six hours.
- Checks Harbor Breeze's official sightings page.
- Checks recent official Harbor Breeze and Aquarium of the Pacific Instagram posts when Instagram's public endpoint is available.
- Checks narrowly filtered recent Google News and Bing News RSS results.
- Posts a comment only to GitHub issue #3 when it finds a new qualifying sighting.
- Uses fingerprints embedded in prior issue comments to prevent duplicate alerts.
- Keeps running after an alert.

GitHub's existing issue-notification emails deliver the alert to John's Gmail. No paid monitoring service, external API key, ChatGPT task slot, or model token is required.

## Timing logic

- Before August 4, 2026: suppress isolated sightings; alert only for sustained, corroborated, or unusually strong blue-whale presence.
- August 4–16, 2026: alert for any new credible recent sighting relevant to a near-term Long Beach departure.
- August 17 onward: frame the alert for the Harbor Breeze/Aquarium family outing with Corinna, Jax, and Quinn.

## Manual test

```bash
python -m pip install -r blue_whale_monitor/requirements.txt
python -m unittest blue_whale_monitor.test_monitor
python -m blue_whale_monitor.monitor --dry-run
```

The live GitHub run receives `GITHUB_TOKEN` automatically and writes only to issue #3 when a new alert qualifies.
