import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { TripPlanResult } from "./TripPlanResult";
import { TripRequestForm } from "./TripRequestForm";
import { bookedRailPlanningPayload } from "./test/bookedRailTripPlanningFixtures";
import {
  createTripPlanningApi,
  parseTripPlanResponse,
  type TripPlanningApi,
} from "./tripPlanningApi";
import { ACTIVE_V4_JOB_STORAGE_KEY } from "./useTripPlanningJob";

async function renderBookedRailForm(onSubmit = vi.fn()) {
  const user = userEvent.setup();
  render(
    <TripRequestForm
      onSubmit={onSubmit}
      initialStartDate="2026-08-21"
      planningToday="2026-08-20"
      createClientRequestId={() => "11111111-1111-4111-8111-111111111111"}
    />,
  );
  await user.click(
    screen.getByRole("radio", { name: "多城市·填写已购铁路车次" }),
  );
  return user;
}

async function completeBookedRailFields(
  user: ReturnType<typeof userEvent.setup>,
) {
  await user.clear(screen.getByLabelText("结束日期 *"));
  await user.type(screen.getByLabelText("结束日期 *"), "2026-08-23");
  const cities = screen.getAllByLabelText("城市 *");
  await user.type(cities[0], "杭州");
  await user.type(cities[1], "上海");
  const accommodations = screen.getAllByLabelText("住宿区域或 POI *");
  await user.type(accommodations[0], "西湖附近");
  await user.type(accommodations[1], "外滩附近");
  await user.type(screen.getByLabelText("车次 *"), " g1234 ");
  await user.type(screen.getByLabelText("出发站 *"), "杭州东站");
  await user.type(screen.getByLabelText("到达站 *"), "上海虹桥站");
  await user.type(screen.getByLabelText("总预算 *"), "5000.00");
}

describe("F-004C booked rail frontend", () => {
  const bookedRailHeading = (_content: string, node: Element | null) =>
    node?.tagName === "STRONG" &&
    node.textContent?.replace(/\s+/g, " ").trim() ===
      "铁路 G1234 · 用户提供，未核验";

  it("keeps V3 as the default and clears segments on explicit V4 selection", async () => {
    const user = userEvent.setup();
    render(
      <TripRequestForm
        onSubmit={vi.fn()}
        initialStartDate="2026-08-21"
        planningToday="2026-08-20"
      />,
    );
    await user.click(
      screen.getByRole("radio", { name: "多城市·自行填写交通段" }),
    );
    expect(
      screen.getByRole("radio", { name: "多城市·自行填写交通段" }),
    ).toBeChecked();
    await user.type(
      screen.getByLabelText("补充要求"),
      "SYNTHETIC_V4_PRIVATE_SENTINEL",
    );
    await user.type(screen.getByLabelText("出发站 *"), "杭州站");
    await user.click(
      screen.getByRole("radio", { name: "多城市·填写已购铁路车次" }),
    );
    expect(screen.getByLabelText("出发站 *")).toHaveValue("");
    expect(screen.getByLabelText("车次 *")).toBeVisible();
    expect(screen.queryByLabelText("补充要求")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("方式 *")).not.toBeInTheDocument();
    expect(
      screen.getByText(/不保存订单号、乘客、证件、座位、二维码或截图/),
    ).toBeVisible();
    await user.click(
      screen.getByRole("radio", { name: "多城市·自行填写交通段" }),
    );
    expect(screen.getByLabelText("补充要求")).toHaveValue("");
  });

  it("normalizes service_number and submits the strict V4 request", async () => {
    const onSubmit = vi.fn();
    const user = await renderBookedRailForm(onSubmit);
    await completeBookedRailFields(user);
    await user.tab();
    expect(screen.getByLabelText("车次 *")).toHaveValue("G1234");
    await user.click(screen.getByRole("button", { name: "生成3日计划" }));
    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onSubmit.mock.lastCall?.[0]).toMatchObject({
      request_version: "4",
      intercity_segments: [
        {
          from_city_index: 0,
          to_city_index: 1,
          mode: "rail",
          service_number: "G1234",
          departure_station: "杭州东站",
          arrival_station: "上海虹桥站",
          departure_at: "2026-08-22T10:00:00+08:00",
          arrival_at: "2026-08-22T12:00:00+08:00",
          fare: null,
        },
      ],
    });
    expect(onSubmit.mock.lastCall?.[0].preferences).toEqual({ interests: [] });
    expect(JSON.stringify(onSubmit.mock.lastCall?.[0])).not.toContain(
      "SYNTHETIC_V4_PRIVATE_SENTINEL",
    );
  });

  it("keeps one strict booked-rail card per adjacent segment for three cities", async () => {
    const user = await renderBookedRailForm();
    await user.click(screen.getByRole("button", { name: "添加第 3 城" }));
    expect(screen.getAllByLabelText("车次 *")).toHaveLength(2);
    expect(screen.getAllByText("铁路 · 用户提供，未核验")).toHaveLength(2);
    expect(screen.queryByLabelText("方式 *")).not.toBeInTheDocument();
  });

  it("fails closed on malformed service_number and focuses the first segment error", async () => {
    const onSubmit = vi.fn();
    const user = await renderBookedRailForm(onSubmit);
    await completeBookedRailFields(user);
    const serviceNumber = screen.getByLabelText("车次 *");
    await user.clear(serviceNumber);
    await user.type(serviceNumber, "G-1234");
    await user.click(screen.getByRole("button", { name: "生成3日计划" }));
    expect(serviceNumber).toHaveFocus();
    expect(serviceNumber).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText(/1—12 位英文字母或数字/)).toBeVisible();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("strictly parses and renders a V4 plan without inventing verification", () => {
    const parsed = parseTripPlanResponse(bookedRailPlanningPayload(true));
    if (!parsed.plan) throw new Error("V4 fixture must contain a plan");
    render(<TripPlanResult response={{ ...parsed, plan: parsed.plan }} />);
    expect(screen.getByText(bookedRailHeading)).toBeVisible();
    expect(screen.getByText(/历时 2 小时/)).toBeVisible();
    expect(screen.getByText("杭州东站 → 上海虹桥站")).toBeVisible();
    expect(screen.getByText("有效期未知，不代表当前有效")).toBeVisible();
    expect(screen.getAllByText(/金额未知|未知/).length).toBeGreaterThan(0);
    expect(screen.queryByText("车次已核实")).toBeNull();
    expect(screen.queryByText("可售")).toBeNull();
    expect(screen.queryByText("已出票")).toBeNull();
    expect(screen.queryByRole("button", { name: "替换活动" })).toBeNull();
  });

  it("rejects V3/V4 tag drift, extra segment keys and malformed service numbers", () => {
    const tagDrift = bookedRailPlanningPayload() as Record<string, unknown>;
    (tagDrift.plan as Record<string, unknown>).plan_format_version = "3";
    expect(() => parseTripPlanResponse(tagDrift)).toThrow();

    const extra = bookedRailPlanningPayload() as Record<string, unknown>;
    const extraPlan = extra.plan as Record<string, unknown>;
    const [extraSegment] = extraPlan.intercity_segments as Array<
      Record<string, unknown>
    >;
    extraPlan.intercity_segments = [{ ...extraSegment, duration_minutes: 120 }];
    expect(() => parseTripPlanResponse(extra)).toThrow();

    const malformed = bookedRailPlanningPayload() as Record<string, unknown>;
    const malformedPlan = malformed.plan as Record<string, unknown>;
    (
      malformedPlan.intercity_segments as Array<Record<string, unknown>>
    )[0].service_number = "G-1234";
    expect(() => parseTripPlanResponse(malformed)).toThrow();
  });

  it("restores a saved V4 job through one same-origin read", async () => {
    const response = parseTripPlanResponse(bookedRailPlanningPayload());
    const api: TripPlanningApi = {
      create: vi.fn(),
      read: vi.fn().mockResolvedValue(response),
      retry: vi.fn(),
    };
    window.localStorage.setItem(ACTIVE_V4_JOB_STORAGE_KEY, response.job_id);
    render(
      <App tripPlanApi={api} pollingPolicy={{ maxPolls: 0, wait: vi.fn() }} />,
    );
    expect(await screen.findByText(bookedRailHeading)).toBeVisible();
    expect(api.read).toHaveBeenCalledWith(
      response.job_id,
      expect.any(AbortSignal),
    );
    expect(api.create).not.toHaveBeenCalled();
    window.localStorage.removeItem(ACTIVE_V4_JOB_STORAGE_KEY);
    await waitFor(() => expect(api.read).toHaveBeenCalledTimes(1));
  });

  it("retries V4 through the existing job URI and accepts only a cleared snapshot", async () => {
    const previous = parseTripPlanResponse(bookedRailPlanningPayload());
    const cleared = {
      ...previous,
      trace_id: "c9000000-0000-4000-8000-000000000004",
      status: "normalizing" as const,
      attempt: 2,
      resolved_destinations: [],
      plan: null,
      violations: [],
      warnings: [],
      uncertainties: [],
      sources: [],
      errors: [],
      retryable: false,
    };
    const request = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(cleared), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const api = createTripPlanningApi(request);

    await expect(api.retry(previous.job_id)).resolves.toEqual(cleared);
    expect(request).toHaveBeenCalledWith(
      `/api/trip-plans/${previous.job_id}/retry`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(request.mock.calls[0][1].body).toBeUndefined();
  });
});
