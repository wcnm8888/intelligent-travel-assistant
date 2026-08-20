import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TripRequestForm } from "./TripRequestForm";

const fixedId = "11111111-1111-4111-8111-111111111111";

async function completeRequiredFields() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("目的地城市 *"), " 杭州 ");
  await user.type(screen.getByLabelText("开始日期 *"), "2026-08-15");
  await user.type(screen.getByLabelText("总预算 *"), "4000.00");
  await user.type(screen.getByLabelText("住宿区域或 POI *"), " 西湖附近 ");
  return user;
}

describe("TripRequestForm", () => {
  it("shows approved defaults and does not expose a separate end date", () => {
    render(
      <TripRequestForm
        onSubmit={vi.fn()}
        initialStartDate="2026-08-15"
        planningToday="2026-08-14"
      />,
    );

    expect(screen.getByLabelText("开始日期 *")).toHaveValue("2026-08-15");
    expect(screen.getByLabelText("结束日期 *")).toHaveValue("2026-08-16");
    expect(screen.getByLabelText("第 1 天开始时间")).toHaveValue("09:00");
    expect(screen.getByLabelText("第 1 天结束时间")).toHaveValue("20:00");
    expect(screen.getByLabelText("第 2 天结束时间")).toHaveValue("18:00");
    expect(screen.getByLabelText("同行人数 *")).toHaveValue(2);
    expect(screen.getByLabelText("餐饮 / 人 / 天")).toHaveValue("100.00");
    expect(screen.getByLabelText("行程节奏")).toHaveValue("balanced");
    expect(screen.getByLabelText("步行")).toBeChecked();
    expect(screen.getByLabelText("公共交通")).toBeChecked();
    expect(screen.getByText("2—7 日 · 单城市")).toBeVisible();
  });

  it("maps user input to the frozen request DTO without using number amounts", async () => {
    const onSubmit = vi.fn();
    render(
      <TripRequestForm
        onSubmit={onSubmit}
        createClientRequestId={() => fixedId}
        planningToday="2026-08-14"
      />,
    );
    const user = await completeRequiredFields();

    await user.click(screen.getByLabelText("自然"));
    await user.click(screen.getByLabelText("历史"));
    await user.type(screen.getByLabelText("一晚住宿费用"), "700.00");
    await user.clear(screen.getByLabelText("餐饮 / 人 / 天"));
    await user.type(screen.getByLabelText("餐饮 / 人 / 天"), "120.50");
    await user.type(screen.getByLabelText("补充要求"), "节奏不要太赶");
    await user.click(screen.getByRole("button", { name: /生成2日计划/ }));

    expect(onSubmit).toHaveBeenCalledWith({
      client_request_id: fixedId,
      city: "杭州",
      start_date: "2026-08-15",
      travelers: 2,
      total_budget: { amount: "4000.00", currency: "CNY" },
      preferences: {
        interests: ["自然", "历史"],
        free_text: "节奏不要太赶",
        hard_constraints: [],
      },
      pace: "balanced",
      transport_modes: ["walking", "public_transit"],
      accommodation: {
        area_or_poi: "西湖附近",
        one_night_cost: { amount: "700.00", currency: "CNY" },
      },
      day_windows: [
        { day_offset: 0, start_time: "09:00:00", end_time: "20:00:00" },
        { day_offset: 1, start_time: "09:00:00", end_time: "18:00:00" },
      ],
      intercity_transport_cost: null,
      meal_budget_per_person_per_day: {
        amount: "120.50",
        currency: "CNY",
      },
    });
  });

  it("keeps unknown accommodation cost as null instead of zero", async () => {
    const onSubmit = vi.fn();
    render(
      <TripRequestForm
        onSubmit={onSubmit}
        createClientRequestId={() => fixedId}
        planningToday="2026-08-14"
      />,
    );
    const user = await completeRequiredFields();

    await user.click(screen.getByRole("button", { name: /生成2日计划/ }));

    expect(onSubmit.mock.calls[0][0].accommodation.one_night_cost).toBeNull();
    expect(onSubmit.mock.calls[0][0].intercity_transport_cost).toBeNull();
  });

  it("shows field errors, links them to controls and focuses the first error", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<TripRequestForm onSubmit={onSubmit} planningToday="2026-08-14" />);

    await user.click(screen.getByRole("button", { name: /生成2日计划/ }));

    const city = screen.getByLabelText("目的地城市 *");
    expect(city).toHaveFocus();
    expect(city).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText(/请输入 2—30 个字符/)).toHaveAttribute(
      "role",
      "alert",
    );
    expect(screen.getByText(/请选择有效的开始日期/)).toBeVisible();
    expect(screen.getByText(/请输入大于 0/)).toBeVisible();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects malformed money and requires one transport mode", async () => {
    const onSubmit = vi.fn();
    render(
      <TripRequestForm
        onSubmit={onSubmit}
        createClientRequestId={() => fixedId}
        planningToday="2026-08-14"
      />,
    );
    const user = await completeRequiredFields();

    await user.clear(screen.getByLabelText("总预算 *"));
    await user.type(screen.getByLabelText("总预算 *"), "12.345");
    await user.click(screen.getByLabelText("步行"));
    await user.click(screen.getByLabelText("公共交通"));
    await user.click(screen.getByRole("button", { name: /生成2日计划/ }));

    expect(screen.getByText(/最多两位小数的总预算/)).toBeVisible();
    expect(screen.getByText(/至少选择一种市内交通/)).toBeVisible();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("disables duplicate submission while a request is in progress", () => {
    render(
      <TripRequestForm
        onSubmit={vi.fn()}
        planningToday="2026-08-14"
        submitting
      />,
    );

    expect(screen.getByRole("button", { name: "正在提交" })).toBeDisabled();
  });

  it("submits an explicit three-day version 2 request with preserved windows", async () => {
    const onSubmit = vi.fn();
    render(
      <TripRequestForm
        onSubmit={onSubmit}
        createClientRequestId={() => fixedId}
        planningToday="2026-08-14"
      />,
    );
    const user = await completeRequiredFields();
    await user.clear(screen.getByLabelText("结束日期 *"));
    await user.type(screen.getByLabelText("结束日期 *"), "2026-08-17");
    await user.clear(screen.getByLabelText("第 2 天开始时间"));
    await user.type(screen.getByLabelText("第 2 天开始时间"), "10:00");
    await user.click(screen.getByRole("button", { name: "生成3日计划" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        request_version: "2",
        start_date: "2026-08-15",
        end_date: "2026-08-17",
        day_windows: [
          { day_offset: 0, start_time: "09:00:00", end_time: "20:00:00" },
          { day_offset: 1, start_time: "10:00:00", end_time: "18:00:00" },
          { day_offset: 2, start_time: "09:00:00", end_time: "18:00:00" },
        ],
      }),
    );
  });

  it("does not overwrite a user-edited end date when the start date changes", async () => {
    const user = userEvent.setup();
    render(<TripRequestForm onSubmit={vi.fn()} planningToday="2026-08-14" />);
    const start = screen.getByLabelText("开始日期 *");
    const end = screen.getByLabelText("结束日期 *");
    await user.type(start, "2026-08-15");
    await user.clear(end);
    await user.type(end, "2026-08-18");
    await user.clear(start);
    await user.type(start, "2026-08-16");

    expect(end).toHaveValue("2026-08-18");
    expect(screen.getByLabelText("第 3 天结束时间")).toBeVisible();
  });

  it("rejects out-of-range dates and focuses an invalid day window", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<TripRequestForm onSubmit={onSubmit} planningToday="2026-08-14" />);
    await user.type(screen.getByLabelText("目的地城市 *"), "杭州");
    await user.type(screen.getByLabelText("开始日期 *"), "2026-08-15");
    await user.clear(screen.getByLabelText("结束日期 *"));
    await user.type(screen.getByLabelText("结束日期 *"), "2026-08-22");
    await user.type(screen.getByLabelText("总预算 *"), "4000.00");
    await user.type(screen.getByLabelText("住宿区域或 POI *"), "西湖附近");
    await user.click(screen.getByRole("button", { name: /生成2日计划/ }));

    expect(screen.getByLabelText("结束日期 *")).toHaveFocus();
    expect(screen.getByText(/连续覆盖 2—7 天/)).toBeVisible();
    expect(onSubmit).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText("结束日期 *"));
    await user.type(screen.getByLabelText("结束日期 *"), "2026-08-17");
    await user.clear(screen.getByLabelText("第 2 天结束时间"));
    await user.type(screen.getByLabelText("第 2 天结束时间"), "08:00");
    await user.click(screen.getByRole("button", { name: "生成3日计划" }));
    expect(screen.getByLabelText("第 2 天结束时间")).toHaveFocus();
    expect(screen.getByText(/不能跨夜/)).toBeVisible();
  });
});
