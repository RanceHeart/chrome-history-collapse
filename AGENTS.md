# Instructions for Agents

Goal: collapse explicitly authorized pagination groups while preserving a useful entry for each group.

## Workflow

1. Establish the intended browser/profile, hostname and pagination format. Prefer existing local browser tooling. Keep discovery narrow and avoid printing history titles or full URLs into the conversation.
2. Obtain a consistent backup with normal SQLite locking. If that requires closing Chrome, coordinate with the user and preserve their work. Never kill a running browser, edit a live History database, or use immutable reads as a backup/verification shortcut.
3. Plan from the backup using `plan.py`. The default minimum is 10 numbered pages. Inspect keep/remove choices privately. Do not broaden scope to unrelated sites or change independent content IDs into pagination.
4. Confirm the existing local CDP connection belongs to that same profile. Inspect `history-app` -> shadow root -> `history-list` and the `deleteItems_` method before adapting the script to a new version. Do not assume internal UI contracts remain stable.
5. Run `apply.mjs` without `--apply` first. Apply only within the user's authorization. Use a dedicated background tab, one sequential deletion worker, and URL/day pairs. Do not navigate the user's active tabs.
6. Wait for Chrome to finish. An interrupted JavaScript call may leave native deletion running. Inspect committed state before retrying; do not start concurrent retries.
7. Obtain a fresh consistent snapshot and run `plan.py --verify`. Report counts, retained-page status, integrity status and the private backup location. Never claim remote deletion was verified without separate evidence.

## Operational Lessons

- A URL visited on several local dates needs separate removal items for those dates. Sending an array of all timestamps under one URL item is insufficient on some Chrome versions.
- Batching reduces request overhead; it does not make native history deletion instant. Parallel requests can be rejected or serialized. Do not repeatedly claim completion based only on a resolved UI promise.
- Never read a database mid-transaction to compute an authoritative progress percentage or validate integrity.
- Missing page 1 means keeping an existing unnumbered page or the lowest recorded page. Do not fabricate history by visiting a new page.
- The retained URL can still have multiple visits on different dates. Removing those extra visits is a separate scope decision.
- Native history deletion can participate in Chrome sync. The snapshot covers local history only; remote-only history and remote completion are outside this recipe's verification.

## Publication Rules

- Use only reserved example domains and invented data in tests and docs.
- Never commit backups, plans, profiles, real domains from browsing, timestamps, CDP endpoint paths, local usernames, private filesystem paths, screenshots or logs.
- Keep runtime artifacts outside this repository; preserve the `.gitignore` allowlist.
- Review the entire staged diff and commit metadata before publishing. Use the user's public GitHub identity and a GitHub noreply email when privacy is requested. Do not add agent co-author trailers.
- Do not run destructive integration tests against the user's daily browser. Use synthetic data and a disposable profile.
