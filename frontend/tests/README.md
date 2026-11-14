# Investigation UI checks

Run `corepack pnpm test` with Node 22.18+ (or Node 24) for the provenance, capability, score and review-state regression checks. `corepack pnpm build` also checks TypeScript.

`investigations.browser.mjs` exports a browser regression suite accepting a Playwright `Page` and optional base URL. Start Vite on port 5178 (`corepack pnpm dev --host 127.0.0.1 --port 5178`) and call its default export with an isolated page from any Playwright runner. The suite supplies every API response, checks all review states at desktop and 375px widths, verifies the API's `stage` assessment envelope, checks enforcement polling/counters/expiry and rejects any non-GET request. It needs no API, provider credentials or real review budget.

Example in an existing Playwright environment:

```js
import checkInvestigations from "./investigations.browser.mjs";
const result = await checkInvestigations(await browser.newPage());
console.log(result);
```

The latest Finnish dashboard overview remains the default home, preserving its Bouncer logo, theme toggle, shadcn/ui navigation and all existing views. The additional Investigations tab uses English, follows both themes and is marked with `lang="en"`.
