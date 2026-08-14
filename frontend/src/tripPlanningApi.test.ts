import { describe, expect, it, vi } from "vitest";

import conflictCase from "../../backend/tests/fixtures/synthetic_hangzhou_conflict.json";
import failedCase from "../../backend/tests/fixtures/synthetic_hangzhou_failed.json";
import needsInputCase from "../../backend/tests/fixtures/synthetic_hangzhou_needs_input.json";
import partialCase from "../../backend/tests/fixtures/synthetic_hangzhou_partial.json";

import {
  createTripPlanningApi,
  parseTripPlanResponse,
  TripPlanningClientError,
} from "./tripPlanningApi";
import {
  FIXED_JOB_ID,
  partialPlanningResponse,
  planningResponse,
  readyPlanningResponse,
} from "./test/tripPlanningFixtures";
import { createInitialTripRequest, toTripPlanRequest } from "./tripRequest";

const requestDto = toTripPlanRequest(
  {
    ...createInitialTripRequest("2026-08-15"),
    city: "杭州",
    totalBudget: "4000.00",
    accommodation: "西湖附近",
  },
  "11111111-1111-4111-8111-111111111111",
);

function jsonResponse(value: unknown, status: number): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("tripPlanningApi", () => {
  it("posts the exact DTO to the same-origin planning endpoint", async () => {
    const request = vi
      .fn()
      .mockResolvedValue(jsonResponse(planningResponse(), 202));
    const api = createTripPlanningApi(request);

    await expect(api.create(requestDto)).resolves.toMatchObject({
      status: "draft",
      job_id: FIXED_JOB_ID,
    });

    expect(request).toHaveBeenCalledTimes(1);
    const [url, init] = request.mock.calls[0];
    expect(url).toBe("/api/trip-plans");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(requestDto);
  });

  it("reads a validated job from the same-origin resource URL", async () => {
    const request = vi
      .fn()
      .mockResolvedValue(jsonResponse(planningResponse("collecting"), 200));
    const api = createTripPlanningApi(request);

    await expect(api.read(FIXED_JOB_ID)).resolves.toMatchObject({
      status: "collecting",
    });
    expect(request).toHaveBeenCalledWith(
      `/api/trip-plans/${FIXED_JOB_ID}`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("posts retry to the same job and accepts only a cleared attempt snapshot", async () => {
    const retried = planningResponse("normalizing", {
      attempt: 2,
      trace_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    });
    const request = vi.fn().mockResolvedValue(jsonResponse(retried, 202));
    const api = createTripPlanningApi(request);

    await expect(api.retry(FIXED_JOB_ID)).resolves.toEqual(retried);
    expect(request).toHaveBeenCalledWith(
      `/api/trip-plans/${FIXED_JOB_ID}/retry`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(request.mock.calls[0][1].body).toBeUndefined();
  });

  it("rejects unsafe retry responses and preserves safe 409 errors", async () => {
    const stale = {
      ...readyPlanningResponse(),
      status: "normalizing" as const,
      attempt: 2,
      trace_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    };
    const staleApi = createTripPlanningApi(
      vi.fn().mockResolvedValue(jsonResponse(stale, 202)),
    );
    const rejectedApi = createTripPlanningApi(
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            trace_id: null,
            error: {
              code: "retry_not_allowed",
              message: "当前任务状态不允许重试。",
              field: null,
              provider: null,
              retryable: false,
            },
          },
          409,
        ),
      ),
    );

    await expect(staleApi.retry(FIXED_JOB_ID)).rejects.toMatchObject({
      code: "response_invalid",
      message: expect.stringContaining("重试快照"),
    });
    await expect(rejectedApi.retry(FIXED_JOB_ID)).rejects.toMatchObject({
      code: "retry_not_allowed",
      retryable: false,
    });
  });

  it("rejects extra fields and malformed core response values", () => {
    expect(() =>
      parseTripPlanResponse({ ...planningResponse(), extra: "not allowed" }),
    ).toThrowError(TripPlanningClientError);
    expect(() =>
      parseTripPlanResponse({ ...planningResponse(), attempt: "1" }),
    ).toThrowError(/无法识别的数据/);
  });

  it.each([
    {
      name: "invalid calendar date",
      value: {
        ...planningResponse(),
        request_summary: {
          ...planningResponse().request_summary,
          start_date: "2026-02-30",
        },
      },
    },
    {
      name: "invalid ISO timestamp",
      value: { ...planningResponse(), created_at: "2026-08-14T24:00:00Z" },
    },
    {
      name: "unknown server error code",
      value: {
        ...planningResponse(),
        errors: [
          {
            code: "provider_raw_error",
            message: "not part of the public contract",
            field: null,
            provider: null,
            retryable: false,
          },
        ],
      },
    },
  ])("rejects $name", ({ value }) => {
    expect(() => parseTripPlanResponse(value)).toThrowError(
      TripPlanningClientError,
    );
  });

  it("uses only a contract-safe HTTP error message", async () => {
    const request = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          trace_id: null,
          error: {
            code: "input_invalid",
            message: "旅行需求格式不符合公开契约。",
            field: "start_date",
            provider: null,
            retryable: false,
          },
        },
        422,
      ),
    );
    const api = createTripPlanningApi(request);

    await expect(api.create(requestDto)).rejects.toMatchObject({
      code: "input_invalid",
      message: "旅行需求格式不符合公开契约。",
      retryable: false,
    });
  });

  it("redacts transport and malformed response details", async () => {
    const networkApi = createTripPlanningApi(
      vi.fn().mockRejectedValue(new Error("sensitive transport detail")),
    );
    const malformedApi = createTripPlanningApi(
      vi
        .fn()
        .mockResolvedValue(
          new Response("private upstream body", { status: 502 }),
        ),
    );

    await expect(networkApi.create(requestDto)).rejects.toMatchObject({
      code: "network_unavailable",
      message: "无法连接本机计划服务，请确认 FastAPI 已启动。",
    });
    await expect(malformedApi.create(requestDto)).rejects.toMatchObject({
      code: "response_invalid",
    });
  });

  it("rejects invalid job IDs before issuing a request", async () => {
    const request = vi.fn();
    const api = createTripPlanningApi(request);

    await expect(api.read("https://example.com/escape")).rejects.toMatchObject({
      code: "response_invalid",
    });
    await expect(api.retry("not-a-job")).rejects.toMatchObject({
      code: "response_invalid",
    });
    expect(request).not.toHaveBeenCalled();
  });

  it.each([readyPlanningResponse(), partialPlanningResponse()])(
    "accepts the strict $status terminal result contract",
    (response) => {
      expect(parseTripPlanResponse(response)).toEqual(response);
    },
  );

  it.each([
    partialCase.response,
    conflictCase.response,
    needsInputCase.response,
    failedCase.response,
  ])("accepts the frozen backend $status terminal fixture", (response) => {
    expect(parseTripPlanResponse(response)).toEqual(response);
  });

  it("rejects duplicate and dangling source records", () => {
    const response = readyPlanningResponse();
    expect(() =>
      parseTripPlanResponse({
        ...response,
        sources: [...response.sources, response.sources[0]],
      }),
    ).toThrowError(/不一致的计划结果/);
    expect(() =>
      parseTripPlanResponse({ ...response, sources: [] }),
    ).toThrowError(/不一致的计划结果/);
  });

  it("rejects forged terminal status combinations", () => {
    expect(() =>
      parseTripPlanResponse({
        ...readyPlanningResponse(),
        retryable: true,
      }),
    ).toThrowError(/不一致的计划结果/);
    expect(() =>
      parseTripPlanResponse({
        ...failedCase.response,
        errors: [],
      }),
    ).toThrowError(/不一致的计划结果/);
    expect(() =>
      parseTripPlanResponse({
        ...needsInputCase.response,
        retryable: true,
      }),
    ).toThrowError(/不一致的计划结果/);
  });

  it("rejects terminal text that resembles a leaked credential", () => {
    expect(() =>
      parseTripPlanResponse({
        ...failedCase.response,
        errors: [
          {
            ...failedCase.response.errors[0],
            message: "Authorization: Bearer secret=must-not-render",
          },
        ],
      }),
    ).toThrowError(/无法识别的数据/);
  });

  it("rejects malformed nested plan data instead of rendering it", () => {
    const withExtraField = readyPlanningResponse() as unknown as Record<
      string,
      unknown
    >;
    const extraPlan = {
      ...(withExtraField.plan as Record<string, unknown>),
      provider_raw: "must not cross the boundary",
    };
    expect(() =>
      parseTripPlanResponse({ ...withExtraField, plan: extraPlan }),
    ).toThrowError(/无法识别的数据/);

    const unknownWithAmount = partialPlanningResponse();
    const plan = unknownWithAmount.plan!;
    const costItems = [...plan.budget_summary.cost_items];
    costItems[costItems.length - 1] = {
      ...costItems[costItems.length - 1],
      amount: { amount: "0.00", currency: "CNY" },
    };
    expect(() =>
      parseTripPlanResponse({
        ...unknownWithAmount,
        plan: {
          ...plan,
          budget_summary: { ...plan.budget_summary, cost_items: costItems },
        },
      }),
    ).toThrowError(/无法识别的数据/);
  });

  it("rejects dangling location references in a terminal plan", () => {
    const response = readyPlanningResponse();
    const plan = response.plan!;
    expect(() =>
      parseTripPlanResponse({
        ...response,
        plan: {
          ...plan,
          days: [
            {
              ...plan.days[0],
              accommodation_location_id: "99999999-9999-4999-8999-999999999999",
            },
            plan.days[1],
          ],
        },
      }),
    ).toThrowError(/无法识别的数据/);
  });

  it("rejects terminal results without a plan or with mismatched request facts", () => {
    expect(() => parseTripPlanResponse(planningResponse("ready"))).toThrowError(
      /不一致的计划结果/,
    );

    const response = readyPlanningResponse();
    const plan = response.plan!;
    expect(() =>
      parseTripPlanResponse({
        ...response,
        plan: {
          ...plan,
          budget_summary: {
            ...plan.budget_summary,
            budget: { amount: "3999.00", currency: "CNY" },
          },
        },
      }),
    ).toThrowError(/不一致的计划结果/);
  });
});
