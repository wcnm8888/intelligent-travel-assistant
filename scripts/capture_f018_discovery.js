// F-018 loopback-only browser acceptance entry for playwright-cli run-code.
async (page) => {
  const origin = "http://127.0.0.1:18118";
  const viewport = page.viewportSize() ?? { width: 1280, height: 900 };
  const label = viewport.width <= 390 ? "mobile-390" : "desktop";
  const requests = [];
  const consoleErrors = [];
  let blockedNonLoopback = 0;
  const allowLoopback = (url) =>
    url === origin ||
    url.startsWith(origin + "/") ||
    url.startsWith("blob:" + origin + "/") ||
    url.startsWith("data:");
  const blockExternal = async (route) => {
    if (allowLoopback(route.request().url())) {
      await route.continue();
      return;
    }
    blockedNonLoopback += 1;
    await route.abort("blockedbyclient");
  };
  const onRequest = (request) => requests.push(request.url());
  const onConsole = (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  };
  await page.route("**/*", blockExternal);
  page.on("request", onRequest);
  page.on("console", onConsole);
  try {
    await page.goto(origin);
    await page.getByRole("button", { name: "查看地图与地点" }).click();

    const search = page.getByRole("button", { name: "搜索", exact: true });
    await search.nth(0).click();
    await page
      .locator("button[data-location-id]")
      .filter({ hasText: "龙翔桥住宿代表锚点" })
      .click();

    await page
      .getByRole("button", { name: "先推荐自然景点，其他都灵活" })
      .click();
    await page.getByRole("button", { name: "发送给旅行顾问" }).click();
    await page.getByRole("heading", { name: "先看看这些建议" }).waitFor();
    const recommendationFirst = await page
      .getByRole("heading", { name: "先看看这些建议" })
      .isVisible();
    const suggestion = page
      .locator(".f017-suggestions li")
      .filter({ hasText: "灵隐寺" })
      .first();
    const recommendationVisible = await suggestion.isVisible();
    await suggestion.getByRole("button", { name: "加入行程" }).click();

    const searchInputs = page.getByRole("textbox", { name: "搜索关键词" });
    await searchInputs.nth(1).fill("西湖");
    await search.nth(1).click();
    await page
      .locator("button[data-location-id]")
      .filter({ hasText: "西湖风景名胜区" })
      .click();
    await page.getByText(/选择一个具体入口/).waitFor();
    await page.getByText(/正在查找/).waitFor({ state: "hidden" });
    const anchorChoices = page
      .locator("button[data-location-id]")
      .filter({ hasText: "断桥残雪入口" });
    await anchorChoices.first().click();
    await page.getByText(/选择一个具体入口/).waitFor({ state: "hidden" });

    await page.screenshot({
      path: `output/f018/20260916-150000-browser-recovery/${label}-selection.png`,
      fullPage: label === "mobile-390",
    });

    await page.getByRole("button", { name: "已选好，补充旅行信息" }).click();
    await page
      .getByRole("button", { name: "保存信息并进入空间预检" })
      .click();
    await page.getByRole("button", { name: "运行空间预检" }).click();
    await page.getByText(/具有不同取舍的可行方案|具有明显取舍的可行方案/).waitFor();

    const optionCards = page.locator(".f015-plan-option");
    const optionCount = await optionCards.count();
    const daySignatures = [];
    for (let index = 0; index < optionCount; index += 1) {
      daySignatures.push(
        await optionCards.nth(index).locator(".f018-option-days").innerText(),
      );
    }
    const uniqueDaySignatures = new Set(daySignatures).size;
    const body = await page.locator("body").innerText();
    const storage = await page.evaluate(() => ({
      local: Object.keys(localStorage),
      session: Object.keys(sessionStorage),
      viewport: innerWidth,
      documentWidth: document.documentElement.scrollWidth,
    }));
    const nonLoopbackRequestCount = requests.filter(
      (url) => !allowLoopback(url),
    ).length;
    const result = {
      recommendation_first: recommendationFirst,
      recommendation_visible: recommendationVisible,
      anchor_completed: !body.includes("选择一个具体入口"),
      selected_two: body.includes("已选择地点\n2"),
      option_count: optionCount,
      unique_day_signatures: uniqueDaySignatures,
      option_days_visible: daySignatures.every(
        (signature) => signature.includes("第 1 天") && signature.includes("交通"),
      ),
      storage,
      console_error_count: consoleErrors.length,
      non_loopback_request_count: nonLoopbackRequestCount,
      blocked_non_loopback_count: blockedNonLoopback,
    };
    const failed = Object.entries({
      recommendation_first: result.recommendation_first,
      recommendation_visible: result.recommendation_visible,
      anchor_completed: result.anchor_completed,
      selected_two: result.selected_two,
      options_present: result.option_count >= 1 && result.option_count <= 3,
      options_distinct: result.unique_day_signatures === result.option_count,
      option_days_visible: result.option_days_visible,
      console_clean: result.console_error_count === 0,
      storage_empty:
        result.storage.local.length === 0 && result.storage.session.length === 0,
      no_horizontal_overflow:
        result.storage.documentWidth <= result.storage.viewport,
      no_non_loopback_attempts:
        result.non_loopback_request_count === 0 &&
        result.blocked_non_loopback_count === 0,
    })
      .filter(([, passed]) => !passed)
      .map(([name]) => name);
    if (failed.length > 0) {
      throw new Error("f018_acceptance_failed:" + failed.join(","));
    }
    return result;
  } finally {
    page.off("request", onRequest);
    page.off("console", onConsole);
    await page.unroute("**/*", blockExternal);
  }
}
