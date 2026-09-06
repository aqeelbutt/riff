// Remix journey on fake tools + fake engine: upload → analysis (stems, lyrics) → style (hybrid default, auto-tune on) → render → A/B result.
const { test, expect } = require("@playwright/test");
const path = require("node:path");
const fs = require("node:fs");

function wavFixture() {
  const p = path.join(__dirname, ".fixture.wav");
  if (!fs.existsSync(p)) {
    const sr = 8000, n = sr, data = Buffer.alloc(44 + n * 2);
    data.write("RIFF", 0); data.writeUInt32LE(36 + n * 2, 4); data.write("WAVE", 8); data.write("fmt ", 12); data.writeUInt32LE(16, 16);
    data.writeUInt16LE(1, 20); data.writeUInt16LE(1, 22); data.writeUInt32LE(sr, 24); data.writeUInt32LE(sr * 2, 28); data.writeUInt16LE(2, 32); data.writeUInt16LE(16, 34);
    data.write("data", 36); data.writeUInt32LE(n * 2, 40);
    for (let i = 0; i < n; i++) data.writeInt16LE(Math.round(3000 * Math.sin(2 * Math.PI * 330 * i / sr)), 44 + i * 2);
    fs.writeFileSync(p, data);
  }
  return p;
}

test("a song you own becomes a remix with your voice in front", async ({ page }) => {
  await page.goto("/remix");
  await expect(page.getByRole("heading", { name: "Remix a song you own" })).toBeVisible();

  // rights first, then the file
  await page.getByRole("checkbox").check();
  await page.getByLabel("Language of the vocals").selectOption("ur");
  await page.locator('input[type="file"]').setInputFiles(wavFixture());

  // analysis → check
  await expect(page.getByRole("heading", { name: /Here's what we heard/ })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("126")).toBeVisible();           // tempo from the fake tools
  await expect(page.getByText("G major")).toBeVisible();
  await expect(page.getByRole("button", { name: /Vocals/ })).toBeVisible();   // a stem chip
  await expect(page.getByLabel("Lyrics")).toHaveValue(/Bolne se sach/);

  // style: hybrid + auto-tune are the defaults
  await page.getByRole("button", { name: /choose a style/ }).click();
  await expect(page.getByRole("button", { name: /Your voice \+ AI backing/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("switch", { name: "Auto-tune" })).toHaveAttribute("aria-checked", "true");
  await expect(page.getByRole("switch", { name: "Harmonies on my voice" })).toHaveAttribute("aria-checked", "false");
  await page.getByRole("button", { name: /Chill Deep House/ }).click();
  await expect(page.getByText(/2 variations/)).toBeVisible();
  await page.getByRole("button", { name: "Remix it" }).click();

  // render → result with the original + two remixes
  await expect(page.getByRole("heading", { name: /Remixing/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Chill Deep House/ })).toBeVisible({ timeout: 40_000 });
  await expect(page.getByRole("button", { name: "Play Original" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Play Remix A/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Play Remix B/ })).toBeVisible();
  await page.getByRole("button", { name: /Play Remix A/ }).click();
  await expect(page.getByLabel("Now playing")).toBeVisible();
  await page.getByRole("button", { name: "♥ Keep" }).first().click();
  await expect(page.getByText("Kept")).toBeVisible();
});
