# Blue-whale monitor closeout

**Date:** 2026-07-24  
**Status:** Incomplete — Gmail filters and final end-to-end validation still require receipts.

## Goal

Replace the ChatGPT monitored task with a persistent zero-token, zero-task-slot monitor for blue-whale sightings relevant to Harbor Breeze / Aquarium of the Pacific departures from Long Beach.

## Result so far

- GitHub Actions checks every six hours.
- The duplicate ChatGPT task is disabled and its slot is recovered.
- The delivery design creates one distinct GitHub issue for each new qualifying sighting.
- The email subject is now plain: `Blue whale near Long Beach — Aug 6`.
- The body is reduced to one evidence sentence, one recommendation, one source link, and the wildlife disclaimer.
- Setup, test, and technical emails were moved to `cc-automated`, archived, and marked read.
- Setup/test GitHub issues were closed.

## Friction and misses

- A one-time sighting incorrectly stopped the original monitor.
- Visualping was treated as actionable before account access and delivery were confirmed.
- ChatGPT task-notification metadata was mistaken for the user's app notification settings.
- The first GitHub delivery looked like CI plumbing rather than a useful alert.
- The existing Gmail Cleanup Apps Script capability was overlooked because the current chat connector cannot create filters.
- A format-only code change was pushed before updating the tests, causing one avoidable failed workflow run.
- Completion was described too early at several points without an end-to-end receipt.

## Durable changes

- Added `task-closeout` to `jlmcnamara/skills-repo` to require receipts, system reconciliation, user-visible testing, cleanup, and a lightweight debrief for consequential work.
- Live sightings now use distinct issues rather than a noisy persistent setup thread.
- Alert presentation follows a deadpan newsletter pattern: specific subject, evidence, recommendation, source.
- Existing Gmail taxonomy is preserved: live alerts go to `Entertainment`; technical monitor mail goes to `cc-automated`.

## Required closeout actions

1. **Validate the workflow**
   - Run `gh run list --repo jlmcnamara/surfbot --workflow "Long Beach blue-whale monitor" --limit 5`.
   - Confirm the newest run after commit `b4b98ba97eeb0a9ddd0c73997ea7b4df58c2e0d3` completed successfully.
   - If not, inspect with `gh run view <RUN_ID> --log-failed`, fix, rerun, and record the successful run URL.

2. **Create persistent Gmail filters through the already-authorized Gmail Cleanup Apps Script**

   Live sighting filter:

   ```text
   from:notifications@github.com subject:"Blue whale near Long Beach"
   ```

   Actions:
   - Add `Entertainment`
   - Add `IMPORTANT`
   - Keep in Inbox
   - Never send to Spam

   Technical failure filter:

   ```text
   from:notifications@github.com subject:"Run failed: Long Beach blue-whale monitor"
   ```

   Actions:
   - Add `cc-automated`
   - Add `IMPORTANT`
   - Keep in Inbox and unread so a silent monitor outage is visible
   - Never send to Spam

   Use the Gmail Cleanup project's existing backup → dry-run → apply → audit discipline. Record the created filter IDs and final criteria/actions.

3. **End-to-end filter test**
   - Create a temporary GitHub issue titled `Blue whale near Long Beach — FILTER TEST` with body `TEST ONLY — not a whale sighting`, then mention `@jlmcnamara` once.
   - Verify the resulting Gmail message is in Inbox, important, and labeled `Entertainment`.
   - Close the test issue.
   - Move the test email to `cc-automated`, mark it read, and archive it.

4. **Remove temporary labels**
   - Confirm `Alerts/Whales` and `System/Monitor Tests` contain zero messages and threads.
   - Delete both labels through the Gmail Cleanup Apps Script.

5. **Final receipt**
   Record:
   - Successful GitHub workflow run URL and timestamp
   - Two Gmail filter IDs and exact actions
   - Gmail message ID or screenshot from the end-to-end filter test
   - Confirmation that the two temporary labels were deleted
   - Confirmation that the ChatGPT whale task remains disabled

## Watchpoints

- A GitHub email titled `Run failed: Long Beach blue-whale monitor` means monitoring may have stopped and must remain visible in Inbox.
- A genuine alert should arrive with a subject beginning `Blue whale near Long Beach —` and the `Entertainment` label.
- No message should be generated when there is no new qualifying sighting.
