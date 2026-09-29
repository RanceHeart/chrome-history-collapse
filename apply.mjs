import fs from 'node:fs';
import {parseArgs} from 'node:util';
import {chromium} from 'playwright-core';

const {values} = parseArgs({options: {
  plan: {type: 'string'}, endpoint: {type: 'string'}, apply: {type: 'boolean', default: false},
}});

async function main() {
  if (!values.plan) throw new Error('A local plan file is required');
  const plan = JSON.parse(fs.readFileSync(values.plan, 'utf8'));
  if (plan.version !== 1 || !Array.isArray(plan.groups) || !Array.isArray(plan.items)) throw new Error('Unsupported plan');
  const keep = new Set(plan.groups.map(group => group.keep));
  const targets = new Set(plan.groups.flatMap(group => group.remove));
  if ([...keep].some(url => targets.has(url))) throw new Error('Keep and remove sets overlap');
  for (const item of plan.items) {
    if (!targets.has(item.url) || !Array.isArray(item.timestamps) || !item.timestamps.length) throw new Error('Invalid removal item');
    for (const timestamp of item.timestamps) {
      const date = new Date(timestamp);
      const localDay = [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-');
      if (!Number.isFinite(timestamp) || localDay !== item.day) throw new Error('Mixed dates or timezone mismatch');
    }
  }
  console.log(JSON.stringify({groups: keep.size, target_urls: targets.size, url_day_pairs: plan.items.length, apply: values.apply}));
  if (!values.apply || !plan.items.length) return;
  if (!values.endpoint) throw new Error('An existing local CDP endpoint is required');
  const endpoint = new URL(values.endpoint);
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(endpoint.hostname)) throw new Error('Only loopback CDP endpoints are supported');
  const browser = await chromium.connectOverCDP(values.endpoint);
  try {
    const cdp = await browser.newBrowserCDPSession();
    const {targetId} = await cdp.send('Target.createTarget', {url: 'chrome://history/', background: true});
    let page;
    for (let attempt = 0; attempt < 50 && !page; attempt++) {
      for (const candidate of browser.contexts().flatMap(context => context.pages())) {
        if (candidate.url() !== 'chrome://history/') continue;
        const session = await candidate.context().newCDPSession(candidate);
        const {targetInfo} = await session.send('Target.getTargetInfo');
        await session.detach();
        if (targetInfo.targetId === targetId) page = candidate;
      }
      if (!page) await new Promise(resolve => setTimeout(resolve, 100));
    }
    if (!page) throw new Error('Could not attach to the dedicated history tab');
    await page.waitForFunction(() => typeof document.querySelector('history-app')?.shadowRoot?.querySelector('history-list')?.deleteItems_ === 'function');
    for (let offset = 0; offset < plan.items.length; offset += 1000) {
      const batch = plan.items.slice(offset, offset + 1000);
      await page.evaluate(async items => {
        const list = document.querySelector('history-app').shadowRoot.querySelector('history-list');
        if (list.pendingDelete) throw new Error('A deletion is already pending');
        try {
          const result = await list.deleteItems_(items.map(item => ({allTimestamps: {[item.url]: item.timestamps}})));
          if (result?.success === false || result?.error) throw new Error('Chrome rejected deletion');
        } finally { list.pendingDelete = false; }
      }, batch);
      console.log(JSON.stringify({completed_url_day_pairs: offset + batch.length, total: plan.items.length}));
    }
    await cdp.send('Target.closeTarget', {targetId});
    console.log('Deletion requests completed. Verify using a fresh consistent snapshot.');
  } finally {
    // Closing a CDP-connected Playwright client disconnects it from the user's browser.
    await browser.close();
  }
}

main().catch(() => {
  // Raw browser exceptions may contain private URLs or local filesystem paths.
  console.error('Stopped. Check the plan, local endpoint and Chrome API compatibility. A submitted batch may still be running; verify before retrying.');
  process.exitCode = 1;
});
