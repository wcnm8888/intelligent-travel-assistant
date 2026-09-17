// F-017 offline browser acceptance entry for playwright-cli run-code.
async (page) => {
  const origin = "http://127.0.0.1:18117";
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
    const textboxes = page.getByRole("textbox");
    await textboxes.nth(1).fill("杭州景点");
    await search.nth(1).click();
    for (const name of [
      "断桥残雪入口",
      "灵隐寺（synthetic）",
      "飞来峰（synthetic）",
    ]) {
      await page
        .locator("button[data-location-id]")
        .filter({ hasText: name })
        .click();
    }

    await page
      .getByLabel("你的补充")
      .fill("老人同行，希望少走路并避开拥挤，上午十点后出发");
    await page.getByRole("button", { name: "发送给旅行顾问" }).click();
    await page.getByRole("button", { name: "确认偏好" }).click();
    await page.getByText("步行承受度：低").waitFor();
    const conversationVisible = await page
      .getByText(/老人同行，希望少走路并避开拥挤/)
      .isVisible();
    const confirmedPreferenceVisible = await page
      .getByText("步行承受度：低")
      .isVisible();
    await page.getByRole("button", { name: "收起" }).click();
    const collapsed = await page
      .getByRole("button", { name: "打开顾问" })
      .isVisible();
    await page.getByRole("button", { name: "打开顾问" }).click();
    await page.getByRole("heading", { name: "这次对话" }).waitFor();

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: `output/f017/20260915-233100-browser-recovery/${label}-advisor.png`,
      fullPage: label === "mobile-390",
    });

    await page.getByRole("button", { name: "已选好，补充旅行信息" }).click();
    await page.getByRole("button", { name: "保存信息并进入空间预检" }).click();
    await page.getByRole("button", { name: "运行空间预检" }).click();
    await page.getByText("选择你更喜欢的可行方案").waitFor();
    await page.getByRole("radio", { name: /节奏更轻松/ }).click();
    await page.getByRole("button", { name: "确认方案并生成行程" }).click();
    await page.getByRole("heading", { name: "行程已生成" }).waitFor();
    const beforeRetry = await page.getByText("AI 游览提示暂不可用").isVisible();
    await page.getByRole("button", { name: "重试 AI 游览提示" }).click();
    await page.getByText("AI 游览提示暂不可用").waitFor({ state: "hidden" });
    const advisorResultLabels = await page.getByText("旅行顾问建议").count();
    await page.getByRole("button", { name: /第 2 日/ }).click();
    const body = await page.locator("body").innerText();
    const map = await page
      .getByRole("region", { name: "地点地图" })
      .innerText();
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
      collapsed_and_reopened: collapsed,
      conversation_visible: conversationVisible,
      confirmed_preference_visible: confirmedPreferenceVisible,
      before_retry_fallback: beforeRetry,
      narrative_recovered: !body.includes("AI 游览提示暂不可用"),
      advisor_result_labels: advisorResultLabels,
      selected_three: body.includes("已选择地点\n3"),
      planned_three: body.includes("实际安排地点\n3"),
      all_three_visible: ["断桥残雪入口", "灵隐寺", "飞来峰"].every((name) =>
        body.includes(name),
      ),
      day_two_markers: map.includes("1") && map.includes("2"),
      storage,
      console_error_count: consoleErrors.length,
      non_loopback_request_count: nonLoopbackRequestCount,
      blocked_non_loopback_count: blockedNonLoopback,
    };
    const failed = Object.entries({
      collapsed_and_reopened: result.collapsed_and_reopened,
      conversation_visible: result.conversation_visible,
      confirmed_preference_visible: result.confirmed_preference_visible,
      before_retry_fallback: result.before_retry_fallback,
      narrative_recovered: result.narrative_recovered,
      advisor_result_labels: result.advisor_result_labels >= 2,
      selected_three: result.selected_three,
      planned_three: result.planned_three,
      all_three_visible: result.all_three_visible,
      day_two_markers: result.day_two_markers,
      console_clean: result.console_error_count === 0,
      storage_empty:
        result.storage.local.length === 0 &&
        result.storage.session.length === 0,
      no_horizontal_overflow:
        result.storage.documentWidth <= result.storage.viewport,
      no_non_loopback_attempts:
        result.non_loopback_request_count === 0 &&
        result.blocked_non_loopback_count === 0,
    })
      .filter(([, passed]) => !passed)
      .map(([name]) => name);
    if (failed.length > 0)
      throw new Error("f017_acceptance_failed:" + failed.join(","));
    return result;
  } finally {
    page.off("request", onRequest);
    page.off("console", onConsole);
    await page.unroute("**/*", blockExternal);
  }
}
