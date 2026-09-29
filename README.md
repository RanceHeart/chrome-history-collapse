# Chrome History Collapse

[English](README.md) | [简体中文](README.zh-CN.md)

An agent-ready recipe for turning long pagination histories into one retained page per group. Plans are local, deletion is explicit, and execution uses Chrome's own history interface.

Supported patterns are numeric fragments (`/read/demo#1`, `#2`, ...) and an explicitly named pagination query parameter (`?page=1`, `?page=2`, ...). Each run is restricted to one exact hostname. Different document paths and different search filters remain separate. Groups need at least 10 distinct page numbers by default. Page 1 wins; otherwise an existing unnumbered URL wins, then the lowest available page number. This retains one **page URL**, not necessarily one visit across every date.

## Agent Quick Start

Read [AGENTS.md](AGENTS.md) first. Requires Python 3.9+, Node.js 20+, and Chrome with an **existing, local CDP connection**. The browser adapter uses a private Chrome UI method, so inspect compatibility after Chrome upgrades.

```sh
npm ci --registry=https://registry.npmjs.org
npm test
```

1. Identify the intended Chrome profile and its `History` database. Obtain a consistent SQLite backup into a private directory outside this repository. SQLite's normal backup command is suitable when the database can be opened normally. If Chrome holds an exclusive lock, arrange a normal browser exit first, then back up. Do not force-kill Chrome or use `immutable=1` to bypass an active writer.

   ```sh
   umask 077
   mkdir -p "$HOME/.local/share/chrome-history-collapse"
   sqlite3 "$CHROME_HISTORY" ".backup '$HOME/.local/share/chrome-history-collapse/before.sqlite'"
   ```

   Set `CHROME_HISTORY` locally to the selected profile's actual History file. The backup command must succeed before proceeding. Keep this backup even after deletion.

2. Make a plan from that snapshot, using the actual hostname only in local commands:

   ```sh
   python3 plan.py "$HOME/.local/share/chrome-history-collapse/before.sqlite" \
     --host example.org \
     --output "$HOME/.local/share/chrome-history-collapse/plan.json"
   ```

   For query pagination, add `--page-param page`. Path-based chapter/page formats require an explicit site-specific rule; do not replace arbitrary numeric IDs. Review the generated keep/remove lists locally. Console output contains counts only.

3. Identify the selected browser's CDP endpoint. If its HTTP discovery endpoint returns 404 but the profile's `DevToolsActivePort` exists, the first line contains the port and the second contains the browser WebSocket path. Combine them as `ws://127.0.0.1:<port><path>` and set `CHROME_CDP` locally. Verify the connection belongs to the same profile used for planning. Never publish this endpoint. If CDP is unavailable, stop and arrange a supported local browser connection; do not silently switch profiles or relaunch the user's browser.

4. Validate without deleting, then apply within the user's authorized scope:

   ```sh
   node apply.mjs --plan "$HOME/.local/share/chrome-history-collapse/plan.json"
   node apply.mjs --plan "$HOME/.local/share/chrome-history-collapse/plan.json" \
     --endpoint "$CHROME_CDP" --apply
   ```

   A dedicated background history tab is used. Leave that tab open while the operation runs. Existing tabs are not reused. Batches run sequentially; large histories can take many minutes. Adding parallel writers does not remove Chrome's database bottleneck. A navigation, lost connection, or failed script is **not** proof that Chrome canceled an already submitted batch.

5. After completion, obtain another consistent snapshot as `after.sqlite`, then verify:

   ```sh
   python3 plan.py "$HOME/.local/share/chrome-history-collapse/after.sqlite" \
     --verify "$HOME/.local/share/chrome-history-collapse/plan.json"
   ```

   Success requires zero remaining target URLs, zero missing retained URLs, and a passing SQLite integrity check. If requests were interrupted, inspect a fresh snapshot before retrying. Only retry residual URL/day pairs; do not launch overlapping deletion jobs.

## Important Details

- **Group deletion items by URL and local calendar date.** Passing all dates for one URL in a single item can leave later visits behind. The planner already splits these items. Run planning and execution in the same time zone.
- **Back up before deleting.** A local SQLite backup is useful for recovery but does not reverse deletion already propagated to other devices or a server. Restore only with Chrome stopped and with explicit authorization for replacing the current history, which can overwrite newer visits.
- **Local verification is not remote verification.** Chrome's native path can issue sync deletion directives when history sync is enabled. This tool neither inventories remote-only history nor confirms deletion on Google's servers or other devices.
- **Use supported snapshots.** A live immutable read can observe an in-progress transaction and even report transient corruption. This recipe deliberately avoids that shortcut.
- **No blanket domain cleanup.** The planner only targets explicit pagination groups. It does not merge every page on a hostname, strip arbitrary fragments, or treat different content IDs as page numbers.

The relevant upstream behavior is in Chromium's [BrowsingHistoryHandler::RemoveVisits](https://source.chromium.org/chromium/chromium/src/+/main:chrome/browser/ui/webui/history/browsing_history_handler.cc) and [BrowsingHistoryService::RemoveVisits](https://source.chromium.org/chromium/chromium/src/+/main:components/history/core/browser/browsing_history_service.cc). These are internal APIs and can change.

## Privacy

This repository contains synthetic examples only. Keep history databases, plans, visit timestamps, browser profiles, screenshots, terminal captures and execution logs outside the repository. The allowlist-based `.gitignore` is an additional guard, not a substitute for reviewing staged files. Never paste real browsing URLs into issues, commits, CI jobs or agent reports. There is no telemetry or upload code; Chrome's own sync behavior still applies.

## Validation

`npm test` uses synthetic in-memory SQLite data to check host/path isolation, pagination filters, page-1 retention and cross-day splitting. It does not touch your real browser. A separate disposable-profile smoke test exercised planning, dry run, native deletion and verification with synthetic pages. The scripts do not claim compatibility with every Chrome version; verify against a disposable profile before adapting the browser interface.

MIT licensed; see [LICENSE](LICENSE).
