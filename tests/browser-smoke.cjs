/* Run with a dev/preview server listening. npx playwright install chromium first.
   BASE_URL=http://localhost:5178 node tests/browser-smoke.cjs
   PLAYWRIGHT_MODULE may point at an existing compatible installation.
*/
const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.BROWSER_EXECUTABLE || undefined,
    args: ["--no-sandbox"],
  });
  const page = await browser.newPage();
  try {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const base = process.env.BASE_URL || "http://localhost:5178";
    await page.goto(base);
    await page
      .getByRole("heading", { name: "Beyond the finishing order." })
      .waitFor();
    await page.getByRole("link", { name: "The model", exact: true }).click();
    await page.locator("#search").fill("alonso");
    await page.waitForFunction(
      () =>
        document.querySelector("#count")?.textContent === "1–1 of 1 drivers",
    );
    assert.match(await page.locator("#rows").textContent(), /Fernando Alonso/);
    assert.match(
      await page.locator("#db-status").textContent(),
      /SQLite runs locally/,
    );
    await page.locator("#search").fill("no_such_driver");
    await page.getByText("No matching drivers. Try fewer filters.").waitFor();
    await page.locator("#search").fill("");
    await page.waitForFunction(
      () => document.querySelectorAll("#rows tr").length === 25,
    );
    await page.locator("#next").click();
    await page.waitForFunction(() =>
      document.querySelector("#count")?.textContent.startsWith("26–"),
    );
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForFunction(
      () => document.documentElement.scrollWidth <= innerWidth,
      { timeout: 3000 },
    );
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "Mobile page overflows viewport",
    );
    await page.getByRole("link", { name: "Journal", exact: true }).click();
    await page.screenshot({ path: "/tmp/f1metrix-mobile.png", fullPage: true });
    // Test article rendering with a clearly synthetic, intercepted fixture, never published data.
    await page.route("**/data/publication.json", async (route) => {
      const response = await route.fetch();
      const data = await response.json();
      data.articles = [
        {
          id: "test",
          date: "2026-01-01",
          title: "Synthetic test article",
          summary: "Only a browser test fixture.",
          status: "test fixture",
          sections: [
            {
              heading: "Test evidence",
              text: "Context matters.",
              sources: ["f1db"],
            },
          ],
          drivers: [
            {
              driverId: "a",
              assessment: "Insufficient evidence.",
              sources: ["f1db"],
            },
          ],
          evaluations: [
            {
              driverId: "a",
              name: "Test Driver",
              position: 1,
              expectedPosition: 1.5,
              low: 1,
              high: 2,
            },
          ],
          evidence: { limitations: ["Synthetic fixture only."] },
          generation: { model: "test", promptVersion: "test" },
          sources: [{ id: "f1db", url: "https://github.com/f1db/f1db" }],
        },
      ];
      await route.fulfill({ json: data });
    });
    await page.goto(base + "/#/article/test");
    await page.reload();
    await page
      .getByRole("heading", { name: "Synthetic test article" })
      .waitFor();
    await page.getByRole("heading", { name: "Test Driver" }).waitFor();
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "Article overflows mobile viewport",
    );
    assert.deepEqual(errors, []);
    console.log(
      "Browser smoke passed: SQLite/WASM, search, empty state, pagination, mobile layout, article chart.",
    );
  } catch (error) {
    console.error(
      "Browser state:",
      await page.evaluate(() => ({
        url: location.href,
        search: document.querySelector("#search")?.value,
        count: document.querySelector("#count")?.textContent,
        status: document.querySelector("#db-status")?.textContent,
        rows: document.querySelector("#rows")?.textContent,
      })),
    );
    await page.screenshot({
      path: "/tmp/f1metrix-browser-failure.png",
      fullPage: true,
    });
    throw error;
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
