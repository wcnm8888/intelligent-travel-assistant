import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { bookedRailPlanningPayload } from "./test/bookedRailTripPlanningFixtures";
import { multicityPlanningPayload } from "./test/multicityTripPlanningFixtures";
import {
  FIXED_JOB_ID,
  multidayPlanningPayload,
  partialPlanningResponse,
  planningResponse,
  readyPlanningResponse,
} from "./test/tripPlanningFixtures";
import {
  parseTripPlanResponse,
  TripPlanningClientError,
  type TripPlanResponseDto,
  type TripPlanningApi,
} from "./tripPlanningApi";
import { addCalendarDays, currentShanghaiDate } from "./tripRequest";
import {
  ACTIVE_JOB_STORAGE_KEY,
  ACTIVE_V3_JOB_STORAGE_KEY,
  ACTIVE_V4_JOB_STORAGE_KEY,
} from "./useTripPlanningJob";

const OLD_V3_JOB_ID = "33333333-3333-4333-8333-333333333333";
const OLD_V4_JOB_ID = "44444444-4444-4444-8444-444444444444";

function apiFor(response: TripPlanResponseDto): TripPlanningApi {
  return {
    create: vi.fn(),
    read: vi.fn().mockResolvedValue(response),
    retry: vi.fn(),
    remove: vi.fn().mockResolvedValue(undefined),
  };
}

function renderApp(api: TripPlanningApi, maxPolls = 0) {
  return render(
    <App
      tripPlanApi={api}
      pollingPolicy={{ maxPolls, wait: vi.fn().mockResolvedValue(undefined) }}
    />,
  );
}

async function submitValidRequest(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("目的地城市 *"), "杭州");
  await user.type(
    screen.getByLabelText("开始日期 *"),
    addCalendarDays(currentShanghaiDate(), 1),
  );
  await user.type(screen.getByLabelText("总预算 *"), "4000.00");
  await user.type(screen.getByLabelText("住宿区域或 POI *"), "西湖附近");
  await user.click(screen.getByRole("button", { name: /生成2日计划/ }));
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("F-006 local job recovery", () => {
  it.each([
    ["legacy", readyPlanningResponse()],
    ["V2", parseTripPlanResponse(multidayPlanningPayload(2))],
  ])(
    "restores a canonical %s job without storing its version",
    async (_, response) => {
      window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, response.job_id);
      const api = apiFor(response);

      renderApp(api);

      expect(await screen.findByText(/代码校验通过/)).toBeVisible();
      expect(api.read).toHaveBeenCalledWith(
        response.job_id,
        expect.any(AbortSignal),
      );
      expect(window.localStorage).toHaveLength(1);
      expect(window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY)).toBe(
        response.job_id,
      );
      await waitFor(() =>
        expect(document.getElementById("plan-stage-title")).toHaveFocus(),
      );
    },
  );

  it.each([
    [
      "V3",
      ACTIVE_V3_JOB_STORAGE_KEY,
      parseTripPlanResponse(multicityPlanningPayload()),
    ],
    [
      "V4",
      ACTIVE_V4_JOB_STORAGE_KEY,
      parseTripPlanResponse(bookedRailPlanningPayload()),
    ],
  ])(
    "migrates a legacy %s pointer only after a matching response",
    async (_, key, response) => {
      window.localStorage.setItem(key, response.job_id);
      const api = apiFor(response);

      renderApp(api);

      expect(
        await screen.findByRole("heading", { name: /3日旅笺/ }),
      ).toBeVisible();
      expect(window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY)).toBe(
        response.job_id,
      );
      expect(window.localStorage.getItem(ACTIVE_V3_JOB_STORAGE_KEY)).toBeNull();
      expect(window.localStorage.getItem(ACTIVE_V4_JOB_STORAGE_KEY)).toBeNull();
    },
  );

  it("prefers canonical over legacy V4 and V3 pointers", async () => {
    const response = readyPlanningResponse();
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, response.job_id);
    window.localStorage.setItem(ACTIVE_V4_JOB_STORAGE_KEY, OLD_V4_JOB_ID);
    window.localStorage.setItem(ACTIVE_V3_JOB_STORAGE_KEY, OLD_V3_JOB_ID);
    const api = apiFor(response);

    renderApp(api);

    await waitFor(() => expect(api.read).toHaveBeenCalledOnce());
    expect(api.read).toHaveBeenCalledWith(
      response.job_id,
      expect.any(AbortSignal),
    );
  });

  it("clears an invalid pointer before any read and focuses the new form", async () => {
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, "not-a-uuid");
    const api = apiFor(readyPlanningResponse());

    renderApp(api);

    expect(
      await screen.findByText("上次本机任务无法恢复，已返回新建。"),
    ).toBeVisible();
    expect(api.read).not.toHaveBeenCalled();
    expect(window.localStorage).toHaveLength(0);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "行前设定" })).toHaveFocus(),
    );
  });

  it("discards only an invalid canonical pointer before restoring legacy V4", async () => {
    const response = parseTripPlanResponse(bookedRailPlanningPayload());
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, "not-a-uuid");
    window.localStorage.setItem(ACTIVE_V4_JOB_STORAGE_KEY, response.job_id);
    const api = apiFor(response);

    renderApp(api);

    expect(
      await screen.findByRole("heading", { name: /3日旅笺/ }),
    ).toBeVisible();
    expect(api.read).toHaveBeenCalledWith(
      response.job_id,
      expect.any(AbortSignal),
    );
    expect(window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY)).toBe(
      response.job_id,
    );
    expect(window.localStorage.getItem(ACTIVE_V4_JOB_STORAGE_KEY)).toBeNull();
  });

  it("clears a missing or expired job without rendering cached output", async () => {
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, FIXED_JOB_ID);
    const api = apiFor(readyPlanningResponse());
    vi.mocked(api.read).mockRejectedValue(
      new TripPlanningClientError("job_not_found", "旅行计划不存在或已过期。"),
    );

    renderApp(api);

    expect(
      await screen.findByText("上次本机任务无法恢复，已返回新建。"),
    ).toBeVisible();
    expect(window.localStorage).toHaveLength(0);
    expect(screen.queryByText("西湖湖滨步行")).not.toBeInTheDocument();
  });

  it.each([
    ["network_unavailable", "无法连接本机计划服务，请确认 FastAPI 已启动。"],
    ["http_error", "本机计划服务暂时无法处理请求。"],
    ["response_invalid", "本机计划服务返回了无法识别的数据。"],
  ])(
    "retains the pointer after %s and can retry recovery",
    async (code, message) => {
      const response = readyPlanningResponse();
      window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, response.job_id);
      const api = apiFor(response);
      vi.mocked(api.read)
        .mockRejectedValueOnce(new TripPlanningClientError(code, message, true))
        .mockResolvedValueOnce(response);
      const user = userEvent.setup();

      renderApp(api);

      expect(
        await screen.findByRole("button", { name: "稍后重试恢复" }),
      ).toBeVisible();
      expect(window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY)).toBe(
        response.job_id,
      );
      await user.click(screen.getByRole("button", { name: "稍后重试恢复" }));
      expect(await screen.findByText(/代码校验通过/)).toBeVisible();
      expect(api.read).toHaveBeenCalledTimes(2);
    },
  );

  it("offers recovery after create succeeds but its first poll fails", async () => {
    const response = planningResponse("draft");
    const api = apiFor(response);
    vi.mocked(api.create).mockResolvedValue(response);
    vi.mocked(api.read)
      .mockRejectedValueOnce(
        new TripPlanningClientError(
          "network_unavailable",
          "无法连接本机计划服务。",
          true,
        ),
      )
      .mockResolvedValueOnce(readyPlanningResponse());
    const user = userEvent.setup();

    renderApp(api, 1);
    await submitValidRequest(user);

    const recovery = await screen.findByRole("button", {
      name: "稍后重试恢复",
    });
    expect(window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY)).toBe(
      response.job_id,
    );
    await user.click(recovery);
    expect(await screen.findByText(/代码校验通过/)).toBeVisible();
  });

  it("recovers from the in-memory job when storage is unavailable", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    const response = planningResponse("draft");
    const api = apiFor(response);
    vi.mocked(api.create).mockResolvedValue(response);
    vi.mocked(api.read)
      .mockRejectedValueOnce(
        new TripPlanningClientError(
          "network_unavailable",
          "无法连接本机计划服务。",
          true,
        ),
      )
      .mockResolvedValueOnce(readyPlanningResponse());
    const user = userEvent.setup();

    renderApp(api, 1);
    await submitValidRequest(user);

    const recovery = await screen.findByRole("button", {
      name: "稍后重试恢复",
    });
    await user.click(recovery);
    expect(await screen.findByText(/代码校验通过/)).toBeVisible();
    expect(api.read).toHaveBeenCalledTimes(2);
  });

  it("offers recovery when resumed polling fails", async () => {
    const draft = planningResponse("draft");
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, draft.job_id);
    const api = apiFor(draft);
    vi.mocked(api.read)
      .mockResolvedValueOnce(draft)
      .mockResolvedValueOnce(planningResponse("normalizing"))
      .mockRejectedValueOnce(
        new TripPlanningClientError(
          "network_unavailable",
          "无法连接本机计划服务。",
          true,
        ),
      )
      .mockResolvedValueOnce(readyPlanningResponse());
    const user = userEvent.setup();

    renderApp(api, 1);
    await user.click(await screen.findByRole("button", { name: "继续刷新" }));

    const recovery = await screen.findByRole("button", {
      name: "稍后重试恢复",
    });
    expect(window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY)).toBe(
      draft.job_id,
    );
    await user.click(recovery);
    expect(await screen.findByText(/代码校验通过/)).toBeVisible();
  });

  it("offers recovery when retry polling fails", async () => {
    const partial = partialPlanningResponse();
    const retrying = planningResponse("normalizing", {
      attempt: 2,
      trace_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    });
    const recovered = {
      ...readyPlanningResponse(),
      attempt: 2,
      trace_id: retrying.trace_id,
    };
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, partial.job_id);
    const api = apiFor(partial);
    vi.mocked(api.retry).mockResolvedValue(retrying);
    vi.mocked(api.read)
      .mockResolvedValueOnce(partial)
      .mockRejectedValueOnce(
        new TripPlanningClientError(
          "response_invalid",
          "本机计划服务返回了无法识别的数据。",
          true,
        ),
      )
      .mockResolvedValueOnce(recovered);
    const user = userEvent.setup();

    renderApp(api, 1);
    await user.click(
      await screen.findByRole("button", { name: "重试缺失数据" }),
    );

    const recovery = await screen.findByRole("button", {
      name: "稍后重试恢复",
    });
    expect(window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY)).toBe(
      partial.job_id,
    );
    await user.click(recovery);
    expect(await screen.findByText(/代码校验通过/)).toBeVisible();
  });

  it("keeps storage failures isolated from a new submission", async () => {
    const get = vi
      .spyOn(Storage.prototype, "getItem")
      .mockImplementation(() => {
        throw new DOMException("blocked", "SecurityError");
      });
    const set = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new DOMException("blocked", "SecurityError");
      });
    const api = apiFor(readyPlanningResponse());
    vi.mocked(api.create).mockResolvedValue(readyPlanningResponse());
    const user = userEvent.setup();

    renderApp(api);
    await submitValidRequest(user);

    expect(await screen.findByText(/代码校验通过/)).toBeVisible();
    expect(api.create).toHaveBeenCalledOnce();
    expect(get).toHaveBeenCalled();
    expect(set).toHaveBeenCalled();
  });

  it("uses inline delete confirmation with deterministic cancel and success focus", async () => {
    const response = readyPlanningResponse();
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, response.job_id);
    const api = apiFor(response);
    const user = userEvent.setup();

    renderApp(api);
    const trigger = await screen.findByRole("button", {
      name: "删除本机任务",
    });
    await user.click(trigger);
    const confirm = screen.getByRole("button", { name: "确认删除" });
    expect(confirm).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(api.remove).not.toHaveBeenCalled();

    await user.click(trigger);
    await user.click(screen.getByRole("button", { name: "确认删除" }));
    expect(api.remove).toHaveBeenCalledWith(
      response.job_id,
      expect.any(AbortSignal),
    );
    expect(window.localStorage).toHaveLength(0);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "行前设定" })).toHaveFocus(),
    );
    expect(screen.queryByText("西湖湖滨步行")).not.toBeInTheDocument();
  });

  it("keeps the terminal job and pointer when delete fails", async () => {
    const response = readyPlanningResponse();
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, response.job_id);
    const api = apiFor(response);
    vi.mocked(api.remove).mockRejectedValue(
      new TripPlanningClientError(
        "network_unavailable",
        "无法连接本机计划服务。",
        true,
      ),
    );
    const user = userEvent.setup();

    renderApp(api);
    await user.click(
      await screen.findByRole("button", { name: "删除本机任务" }),
    );
    await user.click(screen.getByRole("button", { name: "确认删除" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "无法删除本机任务",
    );
    expect(window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY)).toBe(
      response.job_id,
    );
    expect(screen.getByText("西湖湖滨步行")).toBeVisible();
  });

  it("does not expose delete while a restored job is paused", async () => {
    const response = planningResponse("draft");
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, response.job_id);
    const api = apiFor(response);

    renderApp(api);

    expect(await screen.findByText("任务仍在等待")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "删除本机任务" }),
    ).not.toBeInTheDocument();
    await waitFor(() =>
      expect(document.getElementById("plan-stage-title")).toHaveFocus(),
    );
  });

  it("returns to edit by clearing the pointer without deleting the job", async () => {
    const response = readyPlanningResponse();
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, response.job_id);
    const api = apiFor(response);
    const user = userEvent.setup();

    renderApp(api);
    await user.click(
      await screen.findByRole("button", { name: "返回修改需求" }),
    );

    expect(window.localStorage).toHaveLength(0);
    expect(api.remove).not.toHaveBeenCalled();
  });
});
