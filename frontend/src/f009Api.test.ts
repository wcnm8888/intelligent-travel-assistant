import { describe, expect, it, vi } from "vitest";

import { createF009Api, F009ClientError } from "./f009Api";

describe("F-009 V5 strict response parsing", () => {
  it("parses a bounded advisor conversation projection", async () => {
    const snapshot = {
      advisor_version: "1",
      session_id: "session",
      revision: 2,
      phase: "interview",
      conversation: [
        { role: "user", text: "老人同行，希望少走路。" },
        { role: "advisor", text: "是否也希望避开拥挤？" },
      ],
      confirmed_preferences: {
        walking_tolerance: "low",
        crowd_tolerance: null,
        day_start: null,
        food_preferences: [],
        budget_flexibility: null,
        party_notes: ["老人同行"],
      },
      pending_suggestions: [],
      question: "是否也希望避开拥挤？",
      safety_summary: "已确认 2 项偏好，发现 0 个待确认地点。",
    };
    const request = vi.fn(async () => Response.json(snapshot));

    await expect(
      createF009Api(request).getAdvisor?.("session"),
    ).resolves.toEqual(snapshot);
  });

  it("reads the latest preplanning session for bounded conflict recovery", async () => {
    const response = { session_id: "session", revision: 3 };
    const request = vi.fn(async () => Response.json(response));

    await expect(createF009Api(request).getSession("session")).resolves.toEqual(
      response,
    );
    expect(request).toHaveBeenCalledWith(
      "/api/preplanning-sessions/session",
      undefined,
    );
  });

  it("sends an idempotent narrative-only retry action", async () => {
    const request = vi.fn(
      async () =>
        new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );

    await expect(
      createF009Api(request).retryNarrative("job-1", "request-1"),
    ).rejects.toMatchObject({ code: "invalid_response" });
    expect(request).toHaveBeenCalledWith(
      "/api/trip-plans/job-1/narrative-retries",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          request_version: "5",
          client_request_id: "request-1",
        }),
      }),
    );
  });

  it("sends a revision-guarded in-memory trip replacement", async () => {
    const request = vi.fn(
      async () =>
        new Response(JSON.stringify({ revision: 2 }), { status: 200 }),
    );
    const trip = {
      city: "杭州",
      start_date: "2026-10-01",
      end_date: "2026-10-02",
      travelers: 2,
      total_budget: { amount: "3000", currency: "CNY" as const },
      preferences: { interests: [], free_text: "", hard_constraints: [] },
      pace: "balanced" as const,
      transport_modes: ["walking" as const],
      day_windows: [
        { day_offset: 0, start_time: "09:00:00", end_time: "20:00:00" },
        { day_offset: 1, start_time: "09:00:00", end_time: "20:00:00" },
      ],
    };

    await createF009Api(request).updateTrip("session", 1, trip);

    expect(request).toHaveBeenCalledWith(
      "/api/preplanning-sessions/session/trip",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ expected_revision: 1, trip }),
      }),
    );
  });

  it("accepts only the safe projected narrative diagnostic fields", async () => {
    const request = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            response_version: "5",
            job_id: "70000000-0000-4000-8000-000000000001",
            trace_id: "70000000-0000-4000-8000-000000000002",
            client_request_id: "70000000-0000-4000-8000-000000000003",
            status: "failed",
            attempt: 1,
            request_summary: {
              request_version: "5",
              city: "杭州",
              start_date: "2026-10-01",
              end_date: "2026-10-02",
              travelers: 2,
              budget: { amount: "3000.00", currency: "CNY" },
              selected_poi_count: 1,
            },
            plan: null,
            conflicts: [],
            warnings: [],
            errors: [
              {
                code: "model_output_invalid",
                message: "模型说明不可用",
                field: null,
                provider: "deepseek",
                diagnostic_code: "narrative_repair_schema_invalid",
                retryable: false,
              },
            ],
            retryable: false,
            created_at: "2026-09-13T07:00:00Z",
            updated_at: "2026-09-13T07:00:00Z",
          }),
          { status: 202, headers: { "Content-Type": "application/json" } },
        ),
    );

    await expect(
      createF009Api(request).createPlan({} as never),
    ).resolves.toMatchObject({
      errors: [
        {
          diagnostic_code: "narrative_repair_schema_invalid",
          provider: "deepseek",
        },
      ],
    });
  });

  it("rejects an otherwise-shaped V5 response with an extra field", async () => {
    const request = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            response_version: "5",
            job_id: "70000000-0000-4000-8000-000000000001",
            trace_id: "70000000-0000-4000-8000-000000000002",
            client_request_id: "70000000-0000-4000-8000-000000000003",
            status: "failed",
            attempt: 1,
            request_summary: {
              request_version: "5",
              city: "杭州",
              start_date: "2026-10-01",
              end_date: "2026-10-02",
              travelers: 2,
              budget: { amount: "3000.00", currency: "CNY" },
              selected_poi_count: 1,
            },
            plan: null,
            conflicts: [],
            warnings: [],
            errors: [{ code: "provider_unavailable", message: "不可用" }],
            retryable: false,
            created_at: "2026-09-13T07:00:00Z",
            updated_at: "2026-09-13T07:00:00Z",
            provider_raw: "must not cross the boundary",
          }),
          { status: 202, headers: { "Content-Type": "application/json" } },
        ),
    );
    const api = createF009Api(request);

    await expect(api.createPlan({} as never)).rejects.toMatchObject({
      code: "invalid_response",
    } satisfies Partial<F009ClientError>);
  });

  it("accepts a strict MapPlan with route points", async () => {
    const point = { longitude: 120.16, latitude: 30.25 };
    const request = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            map_version: "1",
            job_id: "70000000-0000-4000-8000-000000000001",
            plan_id: "70000000-0000-4000-8000-000000000002",
            coordinate_system: "gcj02",
            accommodation: {
              location_id: "70000000-0000-4000-8000-000000000003",
              name: "住宿",
              coordinate: point,
              visit_order: null,
            },
            days: [
              {
                local_date: "2026-10-01",
                color_token: "day-1",
                markers: [
                  {
                    location_id: "70000000-0000-4000-8000-000000000004",
                    name: "西湖",
                    coordinate: point,
                    visit_order: 1,
                  },
                ],
                routes: [
                  {
                    route_id: "70000000-0000-4000-8000-000000000005",
                    origin_location_id: "70000000-0000-4000-8000-000000000003",
                    destination_location_id:
                      "70000000-0000-4000-8000-000000000004",
                    mode: "walking",
                    distance_meters: 1000,
                    duration_minutes: 15,
                    points: [point, { longitude: 120.17, latitude: 30.26 }],
                  },
                ],
              },
            ],
            warnings: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    );

    await expect(createF009Api(request).readMap("job")).resolves.toMatchObject({
      map_version: "1",
      coordinate_system: "gcj02",
    });
  });
});
