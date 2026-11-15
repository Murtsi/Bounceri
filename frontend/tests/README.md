# Investigation UI checks

Run `corepack pnpm test` with Node 22.18+ (or Node 24) for the provenance, capability, score and review-state regression checks. `corepack pnpm build` also checks TypeScript.

Run the browser checks from `frontend/`:

```sh
corepack pnpm install --frozen-lockfile
corepack pnpm exec playwright install chromium
corepack pnpm run test:browser
```

On Linux, use `corepack pnpm exec playwright install --with-deps chromium` to install the required system libraries too, as CI does. The pinned Playwright library is a development dependency. The runner starts Vite on a free loopback port, launches an isolated headless Chromium page, and closes the server and browser after success or failure. A failed check makes the command fail; the whole suite has a two-minute timeout.

`investigations.browser.mjs` exports the same browser regression suite accepting a Playwright `Page` and optional base URL. The suite supplies every API response, checks all review states at desktop and 375px widths, verifies the API's `stage` assessment envelope, checks enforcement polling/counters/expiry and rejects any non-GET request. It needs no API, provider credentials or real review budget.

Example in an existing Playwright environment:

```js
import checkInvestigations from "./investigations.browser.mjs";
const result = await checkInvestigations(await browser.newPage());
console.log(result);
```

The landing page is the default home, with its gatehouse illustration and API-backed synthetic provenance. Browser checks verify both dashboard CTAs, the sidebar logo returning home, and the explicit `?tab=overview` dashboard route before exercising all existing views. The Bouncer logo, splash/motion, dark-only investigation glass panels and desktop/mobile navigation remain covered. The removed theme toggle stays removed. The Investigations tab uses English, follows the current theme and is marked with `lang="en"`.
