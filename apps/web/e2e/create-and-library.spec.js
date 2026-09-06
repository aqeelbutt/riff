// Create → lyrics → generate → takes → play → Library → song page → keep → delete. Fake providers: seconds, deterministic.
const { test, expect } = require("@playwright/test");

test("a song goes from a few words to the library", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Make a song" })).toBeVisible();

  // compose
  await page.getByRole("button", { name: "late night drive" }).click();
  await page.getByRole("button", { name: "Boom-Bap" }).click();
  await page.getByRole("button", { name: "Write lyrics" }).click();

  // brief + streamed lyrics (fake provider → instant but still streamed over SSE)
  await expect(page.getByRole("heading", { name: "Run With Me" })).toBeVisible();
  await expect(page.getByText(/sections · edit any line/i)).toBeVisible({ timeout: 15_000 });
  const generate = page.getByRole("button", { name: /Generate 2 takes/ });
  await expect(generate).toBeEnabled();

  // section rewrite keeps the editor usable
  const firstSection = page.locator("[contenteditable]").first();
  await firstSection.hover();
  await page.getByRole("button", { name: "Shorter" }).first().click();
  await expect(page.getByText(/Rewritten/)).toBeVisible();

  // render
  await generate.click();
  await expect(page.getByRole("heading", { name: /Rendering/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Play take 1" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Play take 2" })).toBeVisible();

  // play → the app-wide player appears
  await page.getByRole("button", { name: "Play take 1" }).click();
  await expect(page.getByLabel("Now playing")).toBeVisible();

  // library shows it; the player survives navigation
  await page.getByLabel("Main").getByRole("link", { name: "Library" }).click();
  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible();
  const card = page.getByRole("link", { name: /Run With Me/ });
  await expect(card).toBeVisible();
  await expect(page.getByLabel("Now playing")).toBeVisible();

  // search + filter
  await page.getByLabel("Search songs").fill("zzz-no-match");
  await expect(page.getByText(/Nothing matches/)).toBeVisible();
  await page.getByLabel("Search songs").fill("");

  // song page: keep a take, delete the song through the themed dialog
  await card.click();
  await expect(page.getByRole("heading", { name: "Takes" })).toBeVisible();
  await page.getByRole("button", { name: "Keep" }).first().click();
  await expect(page.getByText("Kept")).toBeVisible();
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click();
  await expect(page).toHaveURL(/\/library$/);
  await expect(page.getByText(/Nothing here yet|Nothing matches/)).toBeVisible();
});
