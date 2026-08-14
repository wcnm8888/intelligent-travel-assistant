import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import partialCase from "../../backend/tests/fixtures/synthetic_hangzhou_partial.json";

import {
  readyPlanningResponse,
  partialPlanningResponse,
} from "./test/tripPlanningFixtures";
import { TripPlanResult } from "./TripPlanResult";
import { parseTripPlanResponse } from "./tripPlanningApi";

describe("TripPlanResult", () => {
  it("renders a complete two-day plan from the server result", () => {
    const response = readyPlanningResponse();
    if (!response.plan) throw new Error("ready fixture must include a plan");
    render(<TripPlanResult response={{ ...response, plan: response.plan }} />);

    expect(
      screen.getByRole("heading", { name: /杭州市双日旅笺/ }),
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
});
