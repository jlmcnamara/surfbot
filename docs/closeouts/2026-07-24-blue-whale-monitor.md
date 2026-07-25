# Blue-whale monitor closeout

**Date:** 2026-07-24  
**Status:** Complete — all required operational and delivery receipts are confirmed.

## Goal

Replace the ChatGPT monitored task with a persistent zero-token, zero-task-slot monitor for blue-whale sightings relevant to Harbor Breeze / Aquarium of the Pacific departures from Long Beach.

## Confirmed outcome

- GitHub Actions checks every six hours.
- The delivery design creates one distinct GitHub issue for each qualifying sighting.
- Live alert mail is routed to `Entertainment`; technical failure mail is routed to `cc-automated`.
- The workflow, Gmail filters, user-visible delivery, test cleanup, temporary-label cleanup, and global `task-closeout` installation all have receipts.
- The prior ChatGPT blue-whale monitoring task is disabled; ChatGPT returned `SUCCESS` with `is_enabled: false` at `2026-07-24T19:45:25.930335Z`. No later action in the closeout re-enabled it.

## Receipts

### Workflow

- Commit: `b4b98ba97eeb0a9ddd0c73997ea7b4df58c2e0d3`
- Run: `https://github.com/jlmcnamara/surfbot/actions/runs/30124484948`
- Started: `2026-07-24T20:33:00Z`
- Completed: `2026-07-24T20:33:12Z`
- Conclusion: `success`

### Gmail Apps Script

- Existing script ID: `1Q7yLc352h1q5TII4zOqAQ9ziaMHuiTRSclO5fM_FtqycOsHyNf8yVlpd`
- Run ID: `blue-whale-closeout-20260724T233023Z-217a9a`
- Plan hash: `bfc9f85198e9fed8f89e804e6f7f3ef35ce8ccb1e909c41683b377dbbc65bf82`
- Drive run folder: `https://drive.google.com/drive/folders/1u4hOKcfyTMVisUbCw1R4MFp7uDjJ2b-y`
- Plan file: `11YfH0F9Lvr5WHoXQUj8hNlwHxwrSuuZy`
- Audit receipt: `19hUWFXgaXB_X0BHO1CuibCrm0urfv3Fl`
- Pre-apply backup: `1lf1vECcATI1wDJlsvhJTh6CTC7JRjGus`
- Apply receipt: `1FIMdV681AqeaFPUSaYrBpPpj8_Gd3bM2`
- Independent audit receipt: `1g3i7NV3FvdlW-cIy3WU-anqk3MFQSETZ`

### Persistent filters

1. Live sighting
   - ID: `ANe1BmggY1b2eIyk3m4lYCocgjpCIM5RDl4gp0cvbj9LKw`
   - Query: `from:notifications@github.com subject:"Blue whale near Long Beach"`
   - Add: `Entertainment`, `IMPORTANT`
   - Remove: `SPAM`
   - Keep in Inbox; preserve unread state.
2. Technical failure
   - ID: `ANe1BmjhYITe2zsvhQFd_12Lhe9rSJWlikGxDJqNPLtPUg`
   - Query: `from:notifications@github.com subject:"Run failed: Long Beach blue-whale monitor"`
   - Add: `cc-automated`, `IMPORTANT`
   - Remove: `SPAM`
   - Keep in Inbox and preserve unread state.

### End-to-end delivery

- Successful test issue: `https://github.com/jlmcnamara/surfbot/issues/9`
- Single bot-authored mention run: `https://github.com/jlmcnamara/surfbot/actions/runs/30134233027`
- Gmail message ID: `19f967d4aeae484a`
- Arrival state: `INBOX`, `IMPORTANT`, `UNREAD`, `Entertainment`
- Cleanup state: issue closed; message moved to `cc-automated`, marked read, and archived.
- One-shot workflow removed by commit `2741125a6214bea5194c081d1191fc08521293c6`; public readback returned HTTP 404.
- Attempt #8 was closed with no matching Gmail message after GitHub suppressed a self-authored self-mention.

### Temporary labels

- Pre-delete backup: `17_mn-1mks2X1_OLO-Ta_doEy62Q7iQL3`
- Cleanup receipt: `1osNt8gwfyzfjyuv5wZw6DxeI-Qhj9eyx`
- `Alerts/Whales` (`Label_47`): 0 messages, 0 threads, 0 filter references; deleted.
- `System/Monitor Tests` (`Label_48`): 0 messages, 0 threads, 0 filter references; deleted.
- Gmail label readback returned neither name.

### Task-closeout installation

- Package: `dist/task-closeout.skill`
- Package size: 2,230 bytes
- Package SHA-256: `37EDD75F107A58D87DAA6EFD4C61DAC6039418CD40E0D4AA21E8AF42C3D6DE72`
- Global install: `C:\Users\John\.codex\skills\task-closeout`
- Installed/source `SKILL.md` SHA-256: `B4C5E30EFF8B69E521BC7F74ED53AEFB0305D4C26CF4987186710450514771BB`
- Global trigger count: 1
- Global `AGENTS.md` SHA-256: `9FE8A0E06961A7C183F60E4C0454EB24E87CFF4B200BAB77BEFD940610760B9F`

### ChatGPT task retirement

- Task: `Long Beach Blue Whales`
- Confirmation: ChatGPT task update returned `SUCCESS` and `is_enabled: false`.
- Confirmed at: `2026-07-24T19:45:25.930335Z`
- The task slot was therefore recovered before this GitHub-to-Gmail closeout began.

## Lightweight debrief

- **Goal:** Replace the ChatGPT whale task with a durable GitHub-to-Gmail monitor and close every operational loop.
- **Result:** Workflow, two filters, user-visible delivery, cleanup, ChatGPT task retirement, and skill installation are confirmed.
- **Friction:** GitHub suppresses email for a self-authored self-mention, so the first exact test issue produced no mail.
- **Durable change:** A guarded Apps Script closeout module now enforces backup, dry-run, plan-hash approval, apply, audit, and zero-count label deletion; `task-closeout` is globally installed and triggered.
- **Watchpoint:** A `Run failed: Long Beach blue-whale monitor` email must remain visible in Inbox with `IMPORTANT` and `cc-automated`.

No unresolved closeout items remain.

No Google Calendar update was applicable because this closeout changed no date/time.
