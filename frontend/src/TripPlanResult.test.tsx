import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import partialCase from "../../backend/tests/fixtures/synthetic_hangzhou_partial.json";
import conflictCase from "../../backend/tests/fixtures/synthetic_hangzhou_conflict.json";

import {
  readyPlanningResponse,
  partialPlanningResponse,
  multidayPlanningPayload,
  multidayPartialPlanningPayload,
} from "./test/tripPlanningFixtures";
import { TripPlanResult } from "./TripPlanResult";
import { parseTripPlanResponse } from "./tripPlanningApi";

describe("TripPlanResult", () => {
  it("offers the four frozen structured change operations and restores focus on cancel", async () => {
    const user = userEvent.setup();
    const response = readyPlanningResponse();
    if (!response.plan) throw new Error("ready fixture must include a plan");
    render(<TripPlanResult response={{ ...response, plan: response.plan }} />);

    expect(screen.getAllByRole("button", { name: "替换活动" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "删除活动" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "调整时间" })).toHaveLength(2);
    expect(
      screen.getAllByRole("button", { name: "调整当天顺序" }),
    ).toHaveLength(2);

    const trigger = screen.getAllByRole("button", { name: "调整时间" })[0];
    await user.click(trigger);
    expect(
      screen.getByRole("heading", { name: /调整时间 · 西湖湖滨步行/ }),
    ).toHaveFocus();
    await user.clear(screen.getByLabelText("新的结束时间"));
    await user.type(screen.getByLabelText("新的结束时间"), "09:00");
    await user.click(screen.getByRole("button", { name: "准备影响分析" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "结束时间必须晚于开始时间",
    );
    await user.click(screen.getByRole("button", { name: "取消" }));
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("renders a complete two-day plan from the server result", () => {
    const response = readyPlanningResponse();
    if (!response.plan) throw new Error("ready fixture must include a plan");
    render(<TripPlanResult response={{ ...response, plan: response.plan }} />);

    expect(
      screen.getByRole("heading", { name: /杭州市2日旅笺/ }),
    ).toBeVisible();
    expect(screen.getByText("西湖湖滨步行")).toBeVisible();
    expect(screen.getByText("浙江省博物馆参观")).toBeVisible();
    expect(screen.getByText(/多云 · 26—34℃/)).toBeVisible();
    expect(screen.getByText(/阵雨 · 25—32℃/)).toBeVisible();
    expect(screen.getAllByText(/服务端已校验/)).toHaveLength(4);
    expect(screen.getAllByText("¥2,140.00")).toHaveLength(2);
    expect(screen.getByText("预算可完整判定")).toBeVisible();
    expect(screen.getByText(/本计划包含 DeepSeek AI 生成内容/)).toBeVisible();
    expect(screen.getByRole("link", { name: "和风天气" })).toHaveAttribute(
      "href",
      "https://www.qweather.com",
    );
    expect(
      screen.getByText("https://developer.qweather.com/attribution.html"),
    ).toBeVisible();

    const ticket = screen
      .getByText("门票", { selector: "strong" })
      .closest("li");
    expect(ticket).not.toBeNull();
    expect(within(ticket!).getByText("规则估算")).toBeVisible();
    expect(within(ticket!).getByText("¥0.00")).toBeVisible();
  });

  it("keeps missing weather, routes and unknown costs explicit", () => {
    const response = partialPlanningResponse();
    if (!response.plan) throw new Error("partial fixture must include a plan");
    render(<TripPlanResult response={{ ...response, plan: response.plan }} />);

    expect(screen.getByRole("status")).toHaveTextContent("2 项数据尚未完成");
    expect(screen.getByText("完整预算不可判定")).toBeVisible();
    expect(screen.getByText("天气数据缺失")).toBeVisible();
    expect(
      screen.getAllByText("路线数据缺失，交通时间尚未验证。"),
    ).toHaveLength(2);

    const ticket = screen
      .getByText("门票", { selector: "strong" })
      .closest("li");
    expect(ticket).not.toBeNull();
    expect(within(ticket!).getByText("金额未知")).toBeVisible();
    expect(within(ticket!).getByText("未知")).toBeVisible();
    expect(within(ticket!).queryByText("¥0")).not.toBeInTheDocument();
  });

  it("does not claim provider attribution or AI generation when those sources are absent", () => {
    const response = readyPlanningResponse();
    if (!response.plan) throw new Error("ready fixture must include a plan");
    const systemOnly = response.sources.filter(
      (source) => source.provider === "system",
    );

    render(
      <TripPlanResult
        response={{ ...response, plan: response.plan, sources: systemOnly }}
      />,
    );

    expect(
      screen.queryByRole("link", { name: "和风天气" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "高德地图" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/本计划包含 DeepSeek AI 生成内容/),
    ).not.toBeInTheDocument();
  });

  it("shows partial diagnostics and source freshness from the frozen backend fixture", () => {
    const response = parseTripPlanResponse(partialCase.response);
    if (!response.plan) throw new Error("partial fixture must include a plan");
    render(<TripPlanResult response={{ ...response, plan: response.plan }} />);

    expect(
      screen.getByRole("heading", { name: "数据与校验说明" }),
    ).toBeVisible();
    expect(screen.getByText(/全部交通时间均未验证/)).toBeVisible();
    expect(screen.getByText(/门票费用未知/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "来源与时效" })).toBeVisible();
    expect(screen.getAllByText("高德开放平台")).toHaveLength(2);
    expect(screen.getAllByText("和风天气")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "高德地图" })).toHaveAttribute(
      "href",
      "https://www.amap.com/",
    );
    expect(screen.getByText(/地理位置、POI 和路线数据来源/)).toBeVisible();
    expect(screen.getByText("当前有效")).toBeVisible();
    expect(screen.getAllByText("有效期未知").length).toBeGreaterThan(0);
  });

  it("does not offer replan controls for a conflict baseline", () => {
    const response = parseTripPlanResponse(conflictCase.response);
    if (!response.plan) throw new Error("conflict fixture must include a plan");
    render(<TripPlanResult response={{ ...response, plan: response.plan }} />);

    expect(screen.queryByRole("button", { name: "替换活动" })).toBeNull();
    expect(screen.queryByRole("button", { name: "调整当天顺序" })).toBeNull();
  });

  it("renders a wrapped accessible three-day index and blocks unsupported replan", async () => {
    const user = userEvent.setup();
    const parsed = parseTripPlanResponse(multidayPlanningPayload(3));
    if (!parsed.plan) throw new Error("multiday fixture must include a plan");
    render(<TripPlanResult response={{ ...parsed, plan: parsed.plan }} />);

    expect(
      screen.getByRole("heading", { name: /杭州市3日旅笺/ }),
    ).toBeVisible();
    expect(screen.getByText("3 天")).toBeVisible();
    expect(
      screen.getByRole("navigation", { name: "行程日期导航" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: /第 1 天.*当前日期/ }),
    ).toHaveAttribute("aria-current", "date");
    expect(screen.getByText("第 3 天 synthetic 活动")).toBeVisible();
    expect(screen.queryByRole("button", { name: "替换活动" })).toBeNull();
    expect(screen.getByText(/当前仅支持双日计划局部调整/)).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: /第 3 天.*2026-08-17/ }),
    );
    await waitFor(() =>
      expect(document.getElementById("trip-day-3")).toHaveFocus(),
    );
    expect(document.getElementById("trip-day-3")).toHaveAccessibleName(
      "第 3 天，2026-08-17 行程",
    );
    expect(
      screen.getByRole("button", { name: /第 3 天.*当前日期/ }),
    ).toHaveAttribute("aria-current", "date");
  });

  it("keeps structured replan controls for a tagged version 2 two-day plan", () => {
    const parsed = parseTripPlanResponse(multidayPlanningPayload(2));
    if (!parsed.plan) throw new Error("multiday fixture must include a plan");
    render(<TripPlanResult response={{ ...parsed, plan: parsed.plan }} />);

    expect(screen.getAllByRole("button", { name: "替换活动" })).toHaveLength(2);
    expect(screen.queryByText(/当前仅支持双日计划局部调整/)).toBeNull();
  });

  it("renders all seven days while preserving partial and unknown semantics", () => {
    const parsed = parseTripPlanResponse(multidayPartialPlanningPayload());
    if (!parsed.plan) throw new Error("multiday fixture must include a plan");
    render(<TripPlanResult response={{ ...parsed, plan: parsed.plan }} />);

    expect(
      screen.getByRole("heading", { name: /杭州市7日旅笺/ }),
    ).toBeVisible();
    expect(
      screen.getAllByRole("button", { name: /第 \d 天.*2026-08-/ }),
    ).toHaveLength(7);
    expect(screen.getByText("第 7 天 synthetic 活动")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("2 项数据尚未完成");
    expect(screen.getByText("完整预算不可判定")).toBeVisible();
    expect(screen.getByText("天气数据缺失")).toBeVisible();
    const ticket = screen
      .getByText("门票", { selector: "strong" })
      .closest("li");
    expect(ticket).not.toBeNull();
    expect(within(ticket!).getByText("金额未知")).toBeVisible();
    expect(within(ticket!).queryByText("¥0")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "替换活动" })).toBeNull();
  });

  it("preserves a maximum-length unbroken activity title in the day card", () => {
    const payload = multidayPlanningPayload(3);
    const plan = payload.plan;
    if (!plan) throw new Error("multiday fixture must include a plan");
    const longTitle = "超".repeat(500);
    plan.days[0].activities[0].title = longTitle;
    const parsed = parseTripPlanResponse(payload);
    if (!parsed.plan) throw new Error("multiday fixture must include a plan");

    render(<TripPlanResult response={{ ...parsed, plan: parsed.plan }} />);

    expect(screen.getByText(longTitle)).toBeVisible();
  });
});
