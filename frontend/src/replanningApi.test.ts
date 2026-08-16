import { describe, expect, it, vi } from "vitest";

import { readyPlanningResponse } from "./test/tripPlanningFixtures";
import {
  createReplanningApi,
  parseReplanResponse,
  ReplanningClientError,
} from "./replanningApi";

export const REPLAN_ID = "44444444-4444-4444-8444-444444444444";
export const REPLAN_REQUEST_ID = "55555555-5555-4555-8555-555555555555";

export function awaitingConfirmationResponse() {
  const plan = readyPlanningResponse().plan;
  if (!plan) throw new Error("fixture plan missing");
  return {
    job_id: readyPlanningResponse().job_id,
    replan_id: REPLAN_ID,
    replan_request_id: REPLAN_REQUEST_ID,
    trace_id: "66666666-6666-4666-8666-666666666666",
    baseline_plan_id: plan.plan_id,
    operation: "delete_activity",
    status: "awaiting_confirmation",
    impact: {
      categories: ["budget_risk", "source_refresh"],
      direct_refs: [plan.days[0].activities[0].item_id],
      transitive_refs: [plan.days[0].routes[0].route_id],
      affected_dates: [plan.days[0].local_date],
      route_refs: [plan.days[0].routes[0].route_id],
      budget_effect: null,
      source_actions: [
        {
          source_id: readyPlanningResponse().sources[0].source_id,
          action: "refresh",
          freshness: "unknown_validity",
          reason: "unknown_validity",
        },
      ],
      required_validations: ["route_chain", "budget"],
      confirmation_required: true,
    },
    confirmation_expires_at: "2026-08-14T10:15:00+08:00",
    decision: null,
    result: null,
    change_set: null,
    errors: [],
    created_at: "2026-08-14T10:00:00+08:00",
    updated_at: "2026-08-14T10:00:01+08:00",
  };
}

describe("replanning API", () => {
  it("posts an allowlisted command and reads the Location resource", async () => {
    const payload = awaitingConfirmationResponse();
    const request = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(payload), {
          status: 202,
          headers: {
            Location: `/api/trip-plans/${payload.job_id}/replans/${REPLAN_ID}`,
          },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(payload), { status: 200 }),
      );
    const api = createReplanningApi(request);

    await api.create(payload.job_id, {
      replan_request_id: REPLAN_REQUEST_ID,
      baseline_plan_id: payload.baseline_plan_id,
      command: {
        operation: "delete_activity",
        target_activity_id: payload.impact.direct_refs[0],
      },
    });
    await api.read(payload.job_id, REPLAN_ID);

    expect(request).toHaveBeenNthCalledWith(
      1,
      `/api/trip-plans/${payload.job_id}/replans`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(request).toHaveBeenNthCalledWith(
      2,
      `/api/trip-plans/${payload.job_id}/replans/${REPLAN_ID}`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("fails closed for extra fields and unsafe error text", () => {
    const payload = awaitingConfirmationResponse();
    expect(() =>
      parseReplanResponse({ ...payload, raw_provider_response: {} }),
    ).toThrow(ReplanningClientError);
    expect(() =>
      parseReplanResponse({
        ...payload,
        status: "failed",
        impact: payload.impact,
        errors: [{ code: "internal_error", message: "Authorization: secret" }],
      }),
    ).toThrow(ReplanningClientError);
  });
});
