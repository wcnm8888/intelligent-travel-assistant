import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { TripPlanResult } from "./TripPlanResult";
import { TripRequestForm } from "./TripRequestForm";
import { App } from "./App";
import { multicityPlanningPayload } from "./test/multicityTripPlanningFixtures";
import { parseTripPlanResponse, type TripPlanningApi } from "./tripPlanningApi";
import { ACTIVE_V3_JOB_STORAGE_KEY } from "./useTripPlanningJob";

async function renderMulticityForm(onSubmit = vi.fn()) {
  const user = userEvent.setup();
  render(
    <TripRequestForm
      onSubmit={onSubmit}
      initialStartDate="2026-08-21"
      planningToday="2026-08-20"
    />,
  );
  await user.click(screen.getByRole("radio", { name: "多城市" }));
  return user;
}
const groupCount = (name: RegExp) =>
  screen.getAllByRole("group", { name }).length;
function expectFormGroups(cityCount: number) {
  expect(groupCount(/^第 \d 城(?: ·.*)?$/)).toBe(cityCount);
  expect(groupCount(/城际段/)).toBe(cityCount - 1);
}
const payload = (unknownFare = false) =>
  structuredClone(multicityPlanningPayload(unknownFare)) as Record<
    string,
    unknown
  >;
it("accepts a strict V3 response and renders a user-provided transfer", () => {
  const parsed = parseTripPlanResponse(multicityPlanningPayload(true));
  if (!parsed.plan) throw new Error("V3 fixture must contain a plan");
  render(<TripPlanResult response={{ ...parsed, plan: parsed.plan }} />);
  expect(
    screen.getByRole("heading", { name: /杭州.*上海.*3日旅笺/ }),
  ).toBeVisible();
  expect(screen.getByText("杭州站 → 上海站")).toBeVisible();
  expect(screen.getByText("用户提供，未核验")).toBeVisible();
  expect(screen.getAllByText("金额未知").length).toBeGreaterThan(0);
  expect(screen.queryByText("¥0")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "替换活动" })).toBeNull();
});
it("keeps V3 unknown validity as a disclosed fact without inventing retry", () => {
  const parsed = parseTripPlanResponse(multicityPlanningPayload(true));
  if (!parsed.plan) throw new Error("V3 fixture must contain a plan");
  render(
    <TripPlanResult
      response={{ ...parsed, plan: parsed.plan }}
      onRetry={vi.fn()}
    />,
  );
  expect(screen.getByText("有效期未知，不代表当前有效")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: /重新获取|重试缺失/ }),
  ).toBeNull();
});
it("rejects V3 tag drift, forged user sources and ready-with-unknown", () => {
  const tagDrift = payload();
  (tagDrift.plan as Record<string, unknown>).plan_format_version = "2";
  expect(() => parseTripPlanResponse(tagDrift)).toThrow(/无法识别的数据/);
  const forgedSource = payload();
  (forgedSource.sources as Array<Record<string, unknown>>)[0].provider = "amap";
  expect(() => parseTripPlanResponse(forgedSource)).toThrow(/不一致的计划结果/);
  const unknownReady = payload(true);
  unknownReady.status = "ready";
  expect(() => parseTripPlanResponse(unknownReady)).toThrow(/不一致的计划结果/);
});
it("switches explicitly to two-city mode and submits a V3 request", async () => {
  const onSubmit = vi.fn();
  const user = await renderMulticityForm(onSubmit);
  expectFormGroups(2);
  await user.clear(screen.getByLabelText("结束日期 *"));
  await user.type(screen.getByLabelText("结束日期 *"), "2026-08-23");
  const cities = screen.getAllByLabelText("城市 *");
  await user.type(cities[0], "杭州");
  await user.type(cities[1], "上海");
  const accommodations = screen.getAllByLabelText("住宿区域或 POI *");
  await user.type(accommodations[0], "西湖附近");
  await user.type(accommodations[1], "外滩附近");
  await user.type(screen.getByLabelText("出发站 *"), "杭州站");
  await user.type(screen.getByLabelText("到达站 *"), "上海站");
  await user.type(screen.getByLabelText("总预算 *"), "5000.00");
  await user.click(screen.getByRole("button", { name: "生成3日计划" }));
  expect(onSubmit).toHaveBeenCalledOnce();
  expect(onSubmit.mock.lastCall?.[0]).toMatchObject({
    request_version: "3",
    start_date: "2026-08-21",
    end_date: "2026-08-23",
    city_stays: [
      { city: "杭州", nights: 1 },
      { city: "上海", nights: 1 },
    ],
    intercity_segments: [
      {
        from_city_index: 0,
        to_city_index: 1,
        departure_at: "2026-08-22T10:00:00+08:00",
        arrival_at: "2026-08-22T12:00:00+08:00",
        fare: null,
      },
    ],
  });
});
it("clears adjacent segments after a user-controlled city reorder", async () => {
  const user = await renderMulticityForm();
  const cities = screen.getAllByLabelText("城市 *");
  await user.type(cities[0], "杭州");
  await user.type(cities[1], "上海");
  await user.type(screen.getByLabelText("出发站 *"), "杭州站");
  await user.type(screen.getByLabelText("到达站 *"), "上海站");
  await user.click(screen.getByRole("button", { name: "第 2 城上移" }));
  expect(screen.getAllByLabelText("城市 *")[0]).toHaveValue("上海");
  expect(screen.getByLabelText("出发站 *")).toHaveValue("");
  expect(screen.getByLabelText("到达站 *")).toHaveValue("");
  expect(screen.getByText(/全部城际段已清空/)).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText(/第 1 城 · 上海/)).toHaveFocus());
});
it("adds and removes only a third city with deterministic focus", async () => {
  const user = await renderMulticityForm();
  await user.click(screen.getByRole("button", { name: "添加第 3 城" }));
  expectFormGroups(3);
  expect(screen.getByRole("button", { name: "添加第 3 城" })).toBeDisabled();
  await waitFor(() =>
    expect(screen.getAllByRole("textbox", { name: "城市 *" })[2]).toHaveFocus(),
  );
  await user.click(screen.getByRole("button", { name: "删除第 3 城" }));
  expectFormGroups(2);
  await waitFor(() => expect(screen.getByText(/^第 2 城$/)).toHaveFocus());
});
it("reports field-level multi-city errors and focuses the first city", async () => {
  const user = await renderMulticityForm();
  await user.click(screen.getByRole("button", { name: "生成多城市日计划" }));
  const endDate = screen.getByLabelText("结束日期 *");
  expect(endDate).toHaveFocus();
  expect(endDate).toHaveAttribute("aria-invalid", "true");
  expect(screen.getAllByLabelText("城市 *")[0]).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(screen.getByText(/2 城行程必须连续覆盖 3—7 天/)).toBeVisible();
  expect(screen.getAllByText(/请输入出发站点/)).toHaveLength(1);
});
it("restores a saved V3 job through one same-origin read", async () => {
  const response = parseTripPlanResponse(multicityPlanningPayload());
  const api: TripPlanningApi = {
    create: vi.fn(),
    read: vi.fn().mockResolvedValue(response),
    retry: vi.fn(),
  };
  window.localStorage.setItem(ACTIVE_V3_JOB_STORAGE_KEY, response.job_id);
  render(
    <App tripPlanApi={api} pollingPolicy={{ maxPolls: 0, wait: vi.fn() }} />,
  );
  expect(
    await screen.findByRole("heading", { name: /杭州.*上海.*3日旅笺/ }),
  ).toBeVisible();
  expect(api.read).toHaveBeenCalledWith(
    response.job_id,
    expect.any(AbortSignal),
  );
  expect(api.create).not.toHaveBeenCalled();
  window.localStorage.removeItem(ACTIVE_V3_JOB_STORAGE_KEY);
});
