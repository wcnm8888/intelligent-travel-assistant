// F019 single-page offline evidence. Uses an existing Playwright installation.
// Usage: node scripts/capture_f019_selection.js <new-output-dir> <playwright-module>
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");

async function main() {
  const output = path.resolve(process.argv[2]);
  const { chromium } = require(path.resolve(process.argv[3]));
  const width = Number(process.argv[4] || 1440);
  const height = Number(process.argv[5] || 900);
  const origin = "http://127.0.0.1:18119";
  const fixture = JSON.parse(
    fs.readFileSync(path.join(__dirname, "f019-fixture.json"), "utf8"),
  );
  fs.mkdirSync(output, { recursive: true });
  const journey = JSON.parse(
    fs.readFileSync(path.join(__dirname, "f019-ui7-fixture.json"), "utf8"),
  );
  let conflictNext = false;
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
    viewport: { width, height },
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
    } else if (url.pathname === base + "/trip" && request.method() === "PUT") {
      assert.equal(body.expected_revision, current.revision);
      current = { ...current, trip: body.trip, revision: current.revision + 1 };
      response = current;
    } else if (
      url.pathname === base + "/selection" &&
      request.method() === "PUT"
    ) {
      assert.equal(body.expected_revision, current.revision);
      current = {
        ...current,
        selection: body.selection,
        revision: current.revision + 1,
      };
      response = current;
    } else if (
      url.pathname === base + "/v6/preflight" &&
      request.method() === "POST"
    ) {
      assert.equal(body.expected_revision, current.revision);
      response = {
        ...structuredClone(journey.preflight),
        revision: current.revision,
      };
      if (conflictNext) {
        response.state = "conflicted";
        response.options = [];
        response.conflicts = [
          {
            code: "day_capacity_exceeded",
            message: "离线示例：当天容量不足，请调整后重新预检。",
            location_ids: [fixture.options[1].location_id],
            route_id: null,
            recovery_options: ["move_to_day"],
          },
        ];
      }
    } else if (
      url.pathname === "/api/trip-plans" &&
      request.method() === "POST"
    ) {
      response = journey.result;
    } else if (
      url.pathname === "/api/trip-plans/" + journey.result.job_id + "/map" &&
      request.method() === "GET"
    ) {
      response = journey.map;
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
    viewport: { width, height, dpr: 1 },
    fixture: "F019-UI3-v1",
    geometry: {},
    fonts: {},
    actions: [],
    externalAttempts: 0,
    unknownApi: 0,
  };
  try {
    const capture = async (label, selector) => {
      if (selector) await page.locator(selector).scrollIntoViewIfNeeded();
      else await page.evaluate(() => window.scrollTo(0, 0));
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({
        path: path.join(output, label + ".png"),
        fullPage: false,
      });
      const geometry = await page.evaluate(() => ({
        viewport: innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        active: document.activeElement?.textContent?.slice(0, 80),
      }));
      report.geometry[label] = geometry;
      assert.equal(
        geometry.scrollWidth,
        width,
        label + " no horizontal overflow",
      );
    };
    await page.goto(origin);
    await capture("destination");
    await page.getByRole("link", { name: "跳到地图优先规划" }).focus();
    await page.keyboard.press("Enter");
    assert.equal(
      await page
        .locator("#f019-journey-title")
        .evaluate((el) => el === document.activeElement),
      true,
    );
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
      path: path.join(output, `selection-${width}x${height}.png`),
      fullPage: false,
    });

    report.geometry = await page.evaluate(() => ({
      width: innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      nestedButtons: document.querySelectorAll("button button").length,
    }));
    assert.equal(
      report.geometry.scrollWidth,
      width,
      "No horizontal page overflow",
    );
    assert.equal(report.geometry.nestedButtons, 0);
    const mapBox = await page.locator(".f019-map").boundingBox();
    for (const marker of await page.locator(".f019-map-marker").all()) {
      const box = await marker.boundingBox();
      assert.ok(
        box.x >= mapBox.x && box.x + box.width <= mapBox.x + mapBox.width,
        "Every marker fits map width",
      );
    }
    for (const [label, selector] of [
      ["map", ".f019-map"],
      ["advisor", ".f019-advisor"],
    ]) {
      await page.locator(selector).scrollIntoViewIfNeeded();

      await page.screenshot({
        path: path.join(output, label + "-viewport.png"),
        fullPage: false,
      });
    }
    await page.getByRole("button", { name: "更换住宿", exact: true }).click();
    await page.getByRole("dialog").waitFor();

    await page.screenshot({
      path: path.join(output, "editor.png"),
      fullPage: false,
    });
    await page.keyboard.press("Escape");
    assert.equal(
      await page
        .getByRole("button", { name: "更换住宿", exact: true })
        .evaluate((el) => el === document.activeElement),
      true,
      "Escape restores trigger",
    );
    const search = page.getByRole("textbox", {
      name: "搜索景点；更换住宿请打开住宿编辑",
    });
    await search.fill("不存在的候选");
    await page.getByText("没有匹配的候选地点，试试其他关键词。").waitFor();

    await page.screenshot({
      path: path.join(output, "empty-search.png"),
      fullPage: false,
    });
    await search.fill("");
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
    await page.locator(".f019-advisor").scrollIntoViewIfNeeded();

    await page.screenshot({
      path: path.join(output, "selected-history.png"),
      fullPage: false,
    });
    assert.deepEqual(errors, []);
    assert.deepEqual(unexpected, []);
    await page
      .getByRole("button", { name: "03 比较方案", exact: true })
      .click();
    await page
      .getByRole("heading", { name: /为已选的 2 个地点补充旅行信息/ })
      .waitFor();
    await capture("details");
    await page
      .getByRole("button", { name: "保存信息并进入空间预检", exact: true })
      .click();
    await page
      .getByRole("button", { name: "运行空间预检", exact: true })
      .waitFor();
    await capture("preflight-empty");
    conflictNext = true;
    await page
      .getByRole("button", { name: "运行空间预检", exact: true })
      .click();
    await page
      .getByText("离线示例：当天容量不足，请调整后重新预检。", { exact: false })
      .waitFor();
    await capture("preflight-conflict", ".f015-conflict-recovery");
    assert.equal(
      await page
        .getByRole("button", { name: "确认方案并生成行程", exact: true })
        .count(),
      0,
    );
    conflictNext = false;
    await page
      .getByRole("button", { name: "运行空间预检", exact: true })
      .click();
    await page.locator(".f015-plan-option").waitFor();
    await capture("preflight-options", ".f015-plan-options");
    await page
      .getByRole("button", { name: "确认方案并生成行程", exact: true })
      .click();
    await page.locator(".f009-result").waitFor();
    await capture("result");
    await capture("result-narrative", ".f011-narrative-status");
    await page
      .getByRole("button", { name: "返回选点并重新预检", exact: true })
      .click();
    await page.getByText("已选景点 2", { exact: true }).waitFor();
    await capture("selection-return");
    assert.deepEqual(errors, []);
    assert.deepEqual(unexpected, []);
    report.actions.push(
      "destination keyboard skip",
      "details save through controller",
      "conflict cannot generate",
      "feasible option to degraded result",
      "return preserves selection",
    );
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
