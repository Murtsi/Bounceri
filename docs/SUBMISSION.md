# Submission checklist

## Repository

- [ ] Public, `main` green, README updated with the real pitch and screenshots
- [ ] `LICENSE` present (MIT by default)
- [ ] No `.env`, no keys, no personal data in history (`git log -p -- .env` is empty)
- [ ] Tests pass from a clean clone: `uv run --no-project --python 3.12 --with pytest pytest tests -q`
- [ ] Demo startup instructions match the implemented app; `make dev` is still a scaffold placeholder
- [ ] Scan tracked files, untracked release files and all Git history for credentials
- [ ] Publish only synthetic/sanitised traffic fixtures; exclude real logs and database exports
- [ ] Read `SECURITY.md`; check PRs and compare the release commit with the remote branch
- [ ] Seed data included so judges reproduce the demo
- [ ] Tagged: `git tag -a demo -m "Junction submission" && git push --tags`

## Video (usually ≤ 3 min)

- [ ] 1080p, audio clean, no background noise
- [ ] Problem in the first 15 seconds, product by 30
- [ ] Captions or on-screen text for key claims
- [ ] Uploaded and link-tested from a logged-out browser

## Form

- [ ] Team members and emails entered correctly
- [ ] Track(s) selected; read each track's extra requirements
- [ ] Description mentions the sponsor tech by name
- [ ] Screenshots attached (3–5: hero, core flow, result)
- [ ] Submitted early — 30 minutes before the deadline, not 1

## Presentation

- [ ] Slides exported to PDF as a backup
- [ ] Backup video on the presenting laptop and in the cloud
- [ ] Demo laptop charged, charger packed, adapters packed
