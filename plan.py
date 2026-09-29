"""Plan and verify against consistent, user-supplied SQLite snapshots only."""

import argparse
import collections
import datetime
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

EPOCH_US = 11644473600000000


def page_key(url, host, parameter=None):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or parsed.hostname != host:
        return None
    if parameter:
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        values = [v for k, v in pairs if k == parameter]
        if len(values) != 1 or not values[0].isascii() or not values[0].isdigit():
            return None
        base = urlunsplit(parsed._replace(query=urlencode([(k, v) for k, v in pairs if k != parameter])))
        return base, int(values[0])
    if parsed.fragment.isascii() and parsed.fragment.isdigit():
        return urlunsplit(parsed._replace(fragment='')), int(parsed.fragment)
    return None


def make_plan(db, host, minimum=10, parameter=None):
    rows = list(db.execute('SELECT id, url FROM urls WHERE id IN (SELECT url FROM visits)'))
    by_url = {url: ident for ident, url in rows}
    groups = collections.defaultdict(list)
    for ident, url in rows:
        match = page_key(url, host, parameter)
        if match:
            base, page = match
            groups[base].append((page, ident, url))
    result = []
    for base, entries in groups.items():
        if len({page for page, _, _ in entries}) < minimum:
            continue
        first = [entry for entry in entries if entry[0] == 1]
        keep = min(first) if first else ((0, by_url[base], base) if base in by_url else min(entries))
        if base in by_url and by_url[base] != keep[1]:
            entries.append((0, by_url[base], base))
        result.append({'keep': keep[2], 'remove': [url for _, ident, url in entries if ident != keep[1]]})
    targets = {url for group in result for url in group['remove']}
    visits = collections.defaultdict(list)
    for url, timestamp in db.execute('SELECT urls.url, visit_time FROM visits JOIN urls ON visits.url=urls.id'):
        if url in targets:
            ms = (timestamp - EPOCH_US) / 1000
            day = datetime.datetime.fromtimestamp(ms / 1000).date().isoformat()
            visits[url, day].append(ms)
    return {
        'version': 1,
        'timezone': str(datetime.datetime.now().astimezone().tzinfo),
        'groups': result,
        # Chrome's removal API treats each URL entry as a single local calendar day.
        'items': [{'url': url, 'day': day, 'timestamps': times} for (url, day), times in visits.items()],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--page-param', help='Use this query parameter instead of numeric fragments')
    parser.add_argument('--minimum', type=int, default=10)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify', type=Path, help='Verify an existing plan against a fresh snapshot')
    args = parser.parse_args()
    if not args.snapshot.is_file():
        parser.error('Provide an existing consistent snapshot, not the live browser database')
    db = sqlite3.connect(args.snapshot.resolve().as_uri() + '?mode=ro', uri=True)
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise SystemExit('Snapshot integrity check failed')
    if args.verify:
        plan = json.loads(args.verify.read_text())
        visited = {url for url, in db.execute('SELECT DISTINCT urls.url FROM visits JOIN urls ON visits.url=urls.id')}
        targets = {url for group in plan['groups'] for url in group['remove']}
        kept = {group['keep'] for group in plan['groups']}
        report = {'remaining_target_urls': len(targets & visited), 'missing_kept_urls': len(kept - visited), 'integrity': 'ok'}
        print(json.dumps(report))
        raise SystemExit(1 if report['remaining_target_urls'] or report['missing_kept_urls'] else 0)
    if not args.host or not args.output or args.minimum < 2:
        parser.error('Planning requires --host, --output and --minimum >= 2')
    plan = make_plan(db, args.host, args.minimum, args.page_param)
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        json.dump(plan, handle, indent=2)
    print(json.dumps({'groups': len(plan['groups']), 'target_urls': sum(len(g['remove']) for g in plan['groups']), 'url_day_pairs': len(plan['items'])}))


if __name__ == '__main__':
    main()
