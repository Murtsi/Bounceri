# Demo runbook

## T-30 minutes

- [ ] `make up` healthy, `make dev` running, app open in a fresh browser profile
- [ ] Seed script run: demo account, demo data, clean starting state
- [ ] Backup video recorded (screen + voice), playable offline, on the presenting laptop
- [ ] Second laptop or phone with the app open as failover
- [ ] Do-not-disturb on, notifications off, no personal tabs
- [ ] Browser zoom 110–125% for the back row
- [ ] Phone hotspot ready; venue wifi tested
- [ ] Pitch timer visible

## Run of show

| # | Beat | What you click | What you say |
|---|---|---|---|
| 1 | Start | | "This is the problem..." |
| 2 | Core action | | |
| 3 | Result | | |
| 4 | Wow | | |

## Failure plan

| Failure | Do this |
|---|---|
| App will not start | Switch to backup video, keep narrating |
| Network/API down | Flip to seeded local mode (`OFFLINE=1`) |
| Database corrupt | `make reset-db`, re-seed (takes ~20s) — do not debug on stage |
| Judge interrupts with a question | Answer in one sentence, return to the flow |

## After the demo

- [ ] Stop recording, save any analytics screenshots
- [ ] Note what judges asked — it is your next roadmap
- [ ] Push the final commit and tag `demo`
