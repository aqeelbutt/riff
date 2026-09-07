/** The lyric-sync walkthrough is a first-run overlay: it covers the page on purpose, which would block every
 *  other journey. Journeys mark it seen before the app loads; `coach.spec.js` clears it and walks it deliberately. */
const { test: base } = require("@playwright/test");

const SEEN_KEY = "riff:coach:lyric-sync";

const test = base.extend({
  page: async ({ page }, use) => {
    await page.addInitScript((k) => { try { localStorage.setItem(k, "1"); } catch {} }, SEEN_KEY);
    await use(page);
  },
});

module.exports = { test, expect: base.expect, SEEN_KEY };
