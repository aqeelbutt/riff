// The lyric-sync walkthrough: it runs itself the first time, teaches once across pages, and reopens from "?".
// Uses the base fixture (not ./coach.setup) precisely because this spec wants the coach to appear.
const { test, expect } = require("@playwright/test");

const SEEN_KEY = "riff:coach:lyric-sync";

async function makeSong(page) {
  await page.goto("/");
  await page.getByRole("button", { name: "late night drive" }).click();
  await page.getByRole("button", { name: "Boom-Bap" }).click();
  await page.getByRole("button", { name: "Write lyrics" }).click();
  const generate = page.getByRole("button", { name: /Generate 2 takes/ });
  await expect(generate).toBeEnabled({ timeout: 20_000 });
  await generate.click();
  await expect(page.getByRole("button", { name: "Play take 1" })).toBeVisible({ timeout: 30_000 });
}

test("the walkthrough runs itself once, then lives behind the ? button", async ({ page }) => {
  await makeSong(page);

  await page.getByLabel("Main").getByRole("link", { name: "Library" }).click();
  await page.getByRole("link", { name: /Run With Me/ }).first().click();
  await expect(page.getByRole("heading", { name: "Takes" })).toBeVisible();

  // First run: it opens on its own, pointing at the sync control.
  const coach = page.getByRole("dialog");
  await expect(coach).toBeVisible();
  await expect(coach.getByRole("heading", { name: "Time the words to this take" })).toBeVisible();
  await expect(coach.getByText(/1 of 4/)).toBeVisible();

  // Back only exists past the first step.
  await expect(coach.getByRole("button", { name: "Back" })).toHaveCount(0);
  await coach.getByRole("button", { name: "Next" }).click();
  await expect(coach.getByRole("heading", { name: "Every take gets its own timing" })).toBeVisible();
  await coach.getByRole("button", { name: "Back" }).click();
  await expect(coach.getByText(/1 of 4/)).toBeVisible();

  // Walk it out. The last step finishes rather than advancing.
  for (const step of [1, 2, 3]) await coach.getByRole("button", { name: "Next" }).click();
  await expect(coach.getByText(/4 of 4/)).toBeVisible();
  await coach.getByRole("button", { name: "Got it" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // Seen, so it does not ambush the page again on reload...
  expect(await page.evaluate((k) => localStorage.getItem(k), SEEN_KEY)).toBe("1");
  await page.reload();
  await expect(page.getByRole("heading", { name: "Takes" })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // ...but it is still reachable on purpose.
  await page.getByRole("button", { name: "How lyric sync works" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Skip" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // Clean up so the shared fake-provider DB doesn't leak this song into other specs.
  await page.getByRole("button", { name: "Delete" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click();
  await expect(page).toHaveURL(/\/library$/);
});
