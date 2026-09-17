// F019 single-page offline evidence. Uses an existing Playwright installation.
// Usage: node scripts/capture_f019_selection.js <new-output-dir> <playwright-module>
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");

async function main() {
  const output = path.resolve(process.argv[2]);
  const { chromium } = require(path.resolve(process.argv[3]));
  const origin = "http://127.0.0.1:18119";
  const fixture = JSON.parse(
    fs.readFileSync(path.join(__dirname, "f019-fixture.json"), "utf8"),
  );
  fs.mkdirSync(output, { recursive: true });
  const requests = [];
  const errors = [];
  const unexpected = [];
  const actions = [];
  let current = structuredClone(fixture.session);
  let advisor = {
    ...structuredClone(fixture.advisor),
    phase: "interview",
    conversation: [],
    pending_suggestions: [],
    question: "先告诉我你想看什么？",
  };
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: "zh-CN",
    reducedMotion: "reduce",
    serviceWorkers: "block",
  });
  const page = await context.newPage();
  page.on("console", (entry) => {
    if (entry.type() === "error" || entry.type() === "warning")
      errors.push({ type: entry.type(), text: entry.text() });
  });
  page.on("pageerror", (entry) =>
    errors.push({ type: "pageerror", text: entry.message }),
  );
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    requests.push({ method: request.method(), url: request.url() });
    if (url.origin !== origin) {
      unexpected.push({ kind: "external", url: request.url() });
      await route.abort("blockedbyclient");
      return;
    }
    if (!url.pathname.startsWith("/api/")) {
      await route.continue();
      return;
    }
    const body = request.postDataJSON();
    const base = `/api/preplanning-sessions/${current.session_id}`;
    let response;
    if (
      url.pathname === "/api/preplanning-sessions" &&
      request.method() === "POST"
    )
      response = current;
    else if (url.pathname === base && request.method() === "GET")
      response = current;
    else if (url.pathname === `${base}/pois` && request.method() === "GET") {
      const purpose = url.searchParams.get("purpose");
      response = {
        session_id: current.session_id,
        revision: current.revision,
        state: "needs_confirmation",
        page: 1,
        page_size: 20,
        has_more: false,
        items: fixture.options.filter((item) => item.purpose === purpose),
        calls: current.calls,
      };
    } else if (url.pathname === `${base}/advisor` && request.method() === "GET")
      response = advisor;
    else if (
      url.pathname === `${base}/advisor-turns` &&
      request.method() === "POST"
    ) {
      assert.equal(body.message, fixture.advisor.conversation[0].text);
      advisor = structuredClone(fixture.advisor);
      response = advisor;
    } else if (
      url.pathname === `${base}/advisor-actions` &&
      request.method() === "POST"
    ) {
      assert.equal(body.expected_revision, current.revision);
      actions.push(body);
      if (body.action === "accept")
        current = {
          ...current,
          revision: current.revision + 1,
          selection: body.selection_context,
        };
      advisor = {
        ...advisor,
        revision: current.revision,
        pending_suggestions: advisor.pending_suggestions.filter(
          (item) => item.suggestion_id !== body.suggestion_id,
        ),
      };
      response = advisor;
    } else {
      unexpected.push({
        kind: "unknown_api",
        method: request.method(),
        path: url.pathname,
      });
      await route.fulfill({
        status: 599,
        json: {
          error: {
            code: "unmocked_api",
            message: "UI-5 mock does not support this request",
          },
        },
      });
      return;
    }
    await route.fulfill({ status: 200, json: response });
  });
  const report = {
    status: "IN_PROGRESS",
    origin,
    viewport: { width: 1440, height: 900, dpr: 1 },
    fixture: "F019-UI3-v1",
    geometry: {},
    fonts: {},
    actions: [],
    externalAttempts: 0,
    unknownApi: 0,
  };
  try {
    await page.goto(origin);
    await page.getByRole("button", { name: "查看地图与地点" }).click();
    await page.getByRole("button", { name: "选择住宿", exact: true }).click();
    const editor = page.getByRole("dialog", { name: "编辑住宿与地点" });
    await editor
      .getByRole("button", { name: "搜索", exact: true })
      .nth(0)
      .click();
    await editor.getByRole("button", { name: /龙翔桥住宿锚点/ }).click();
    await editor.getByRole("button", { name: "返回选点", exact: true }).click();
    await page
      .getByRole("button", {
        name: fixture.advisor.conversation[0].text,
        exact: true,
      })
      .click();
    await page.getByRole("button", { name: "发送给旅行顾问" }).click();
    await page.getByText("2 条建议，等你确认", { exact: true }).waitFor();
    await page.evaluate(async () => {
      await document.fonts.load('400 14px "Noto Sans SC"', "自然景点");
      await document.fonts.load('500 28px "Noto Serif SC"', "杭州");
      await document.fonts.ready;
      document.activeElement?.blur();
      await new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      );
    });
    await page.screenshot({
      path: path.join(output, "selection-1440x900.png"),
      fullPage: false,
    });
    report.geometry = await page.evaluate(() => {
      const selectors = [
        ".f019-header",
        ".f019-context",
        ".f019-locations",
        ".f019-map",
        ".f019-advisor",
        ".f019-composer",
        ".f019-suggestion",
      ];
      const boxes = Object.fromEntries(
        selectors.map((selector) => [
          selector,
          [...document.querySelectorAll(selector)].map((node) => {
            const r = node.getBoundingClientRect();
            const c = getComputedStyle(node);
            return {
              x: r.x,
              y: r.y,
              width: r.width,
              height: r.height,
              bottom: r.bottom,
              font: c.font,
              color: c.color,
              background: c.backgroundColor,
            };
          }),
        ]),
      );
      return {
        boxes,
        innerWidth,
        innerHeight,
        dpr: devicePixelRatio,
        horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
        verticalOverflow: document.documentElement.scrollHeight > innerHeight,
        nestedButtons: document.querySelectorAll("button button").length,
        inputLength: document.querySelector("#f019-message").value.length,
        locationIds: [
          ...document.querySelectorAll(".f019-locations [data-location-id]"),
        ].map((el) => el.dataset.locationId),
        markerIds: [...document.querySelectorAll("[data-map-location-id]")].map(
          (el) => el.dataset.mapLocationId,
        ),
        suggestionIds: [
          ...document.querySelectorAll("[data-suggestion-id]"),
        ].map((el) => el.dataset.suggestionId),
      };
    });
    const cdp = await context.newCDPSession(page);
    await cdp.send("DOM.enable");
    await cdp.send("CSS.enable");
    const { root } = await cdp.send("DOM.getDocument");
    for (const selector of [
      "#f019-title",
      ".f019-request p",
      ".f019-location h4",
      ".f019-brand strong",
    ]) {
      const { nodeId } = await cdp.send("DOM.querySelector", {
        nodeId: root.nodeId,
        selector,
      });
      report.fonts[selector] = (
        await cdp.send("CSS.getPlatformFontsForNode", { nodeId })
      ).fonts;
    }
    await cdp.detach();
    const boxes = report.geometry.boxes;
    assert.equal(report.geometry.dpr, 1);
    assert.equal(report.geometry.horizontalOverflow, false);
    assert.equal(report.geometry.verticalOverflow, false);
    assert.equal(report.geometry.nestedButtons, 0);
    assert.equal(boxes[".f019-header"][0].height, 72);
    assert.equal(boxes[".f019-context"][0].height, 92);
    for (const [selector, width] of [
      [".f019-locations", 312],
      [".f019-map", 664],
      [".f019-advisor", 384],
    ]) {
      assert.equal(boxes[selector][0].width, width);
      assert.equal(boxes[selector][0].height, 712);
      assert.equal(boxes[selector][0].y, 164);
    }
    // Frozen node 9:105: y=595 within panel at y=164, height=100.
    assert.equal(boxes[".f019-composer"][0].y, 759);
    assert.equal(boxes[".f019-composer"][0].height, 100);
    assert.equal(boxes[".f019-composer"][0].bottom, 859);
    assert.equal(boxes[".f019-suggestion"].length, 2);
    assert.ok(
      boxes[".f019-suggestion"].every(
        (box) => box.bottom < boxes[".f019-composer"][0].y,
      ),
    );
    assert.deepEqual(
      report.geometry.locationIds,
      fixture.options.map((item) => item.location_id),
    );
    assert.deepEqual(
      report.geometry.markerIds,
      fixture.options.map((item) => item.location_id),
    );
    assert.ok(
      report.fonts["#f019-title"].some(
        (font) =>
          font.familyName.includes("Noto Serif SC") && font.glyphCount > 0,
      ),
    );
    assert.ok(
      report.fonts[".f019-request p"].some(
        (font) =>
          font.familyName.includes("Noto Sans SC") && font.glyphCount > 0,
      ),
    );
    const list = page.getByRole("region", { name: "地点清单" });
    const advice = page.getByRole("complementary", { name: "旅行顾问" });
    const card = list.getByRole("article", { name: fixture.options[1].name });
    const marker = page.getByRole("button", {
      name: `地图定位：${fixture.options[1].name}`,
    });
    const beforeFocus = await marker.boundingBox();
    await card.getByRole("button", { name: "地图查看", exact: true }).click();
    assert.equal(
      await marker.evaluate((node) => node === document.activeElement),
      true,
    );
    assert.notEqual((await marker.boundingBox()).x, beforeFocus.x);
    await marker.click();
    assert.equal(
      await card.evaluate((node) => node === document.activeElement),
      true,
    );
    await page.getByRole("button", { name: "放大地图" }).click();
    await advice
      .getByRole("article", { name: fixture.options[1].name })
      .getByRole("button", { name: "地图查看" })
      .click();
    assert.equal(
      await page.locator(".f019-map").getAttribute("data-focus-sequence"),
      "2",
    );
    await page.getByRole("button", { name: "查看全部", exact: true }).click();
    assert.equal((await marker.boundingBox()).x, beforeFocus.x);
    assert.equal(actions.length, 0);
    await card.getByRole("button", { name: "加入已选", exact: true }).click();
    await advice
      .getByRole("article", { name: fixture.options[2].name })
      .getByRole("button", { name: "加入已选", exact: true })
      .click();
    await page.getByText("1 条建议待确认", { exact: true }).waitFor();
    assert.deepEqual(
      current.selection.pois.map((item) => item.location_id),
      fixture.options.slice(1).map((item) => item.location_id),
    );
    await advice
      .getByRole("article", { name: fixture.options[1].name })
      .getByRole("button", { name: "忽略", exact: true })
      .click();
    await page.getByText("0 条建议待确认", { exact: true }).waitFor();
    assert.equal(current.selection.pois.length, 2);
    report.actions.push(
      "two-way focus, repeat focus, zoom and fit",
      "list A then advisor B preserved both",
      "ignore did not remove or add selected locations",
    );
    await page.getByRole("button", { name: /查看对话记录/ }).click();
    const composerBefore = await page.locator(".f019-composer").boundingBox();
    await page.locator(".f019-advisor-scroll").evaluate((node) => {
      node.scrollTop = node.scrollHeight;
    });
    assert.deepEqual(
      await page.locator(".f019-composer").boundingBox(),
      composerBefore,
    );
    report.actions.push("composer fixed while history scrolls");
    assert.deepEqual(errors, []);
    assert.deepEqual(unexpected, []);
    report.status = "PASS";
  } catch (error) {
    report.status = "FAIL";
    report.failure = {
      name: error.name,
      message: error.message,
      stack: error.stack,
    };
    await page.screenshot({
      path: path.join(output, "failure.png"),
      fullPage: false,
    });
    process.exitCode = 1;
  } finally {
    report.externalAttempts = unexpected.filter(
      (entry) => entry.kind === "external",
    ).length;
    report.unknownApi = unexpected.filter(
      (entry) => entry.kind === "unknown_api",
    ).length;
    fs.writeFileSync(
      path.join(output, "browser-report.json"),
      JSON.stringify(report, null, 2),
    );
    fs.writeFileSync(
      path.join(output, "network.json"),
      JSON.stringify({ requests, unexpected, errors, actions }, null, 2),
    );
    await browser.close();
    console.log(
      JSON.stringify(
        {
          status: report.status,
          failure: report.failure?.message,
          externalAttempts: report.externalAttempts,
          unknownApi: report.unknownApi,
          output,
        },
        null,
        2,
      ),
    );
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
