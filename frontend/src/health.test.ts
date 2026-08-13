import { describe, expect, it, vi } from "vitest";

import { HealthCheckError, fetchHealth } from "./health";

function response(body: unknown, ok = true): Response {
  return { ok, json: vi.fn().mockResolvedValue(body) } as unknown as Response;
}

describe("fetchHealth", () => {
  it("accepts only the exact backend health contract", async () => {
    const request = vi
      .fn()
      .mockResolvedValue(
        response({ status: "ok", service: "intelligent-travel-assistant-api" }),
      );

    await expect(fetchHealth(request)).resolves.toEqual({
      status: "ok",
      service: "intelligent-travel-assistant-api",
    });
    expect(request).toHaveBeenCalledWith("/api/health", {
      headers: { Accept: "application/json" },
    });
  });

  it.each([
    { status: "degraded", service: "intelligent-travel-assistant-api" },
    { status: "ok" },
    { status: "ok", service: "intelligent-travel-assistant-api", extra: true },
  ])("rejects a malformed response without exposing it: %j", async (body) => {
    const request = vi.fn().mockResolvedValue(response(body));

    await expect(fetchHealth(request)).rejects.toBeInstanceOf(HealthCheckError);
  });

  it("maps transport and HTTP failures to a safe local error", async () => {
    const request = vi.fn().mockResolvedValue(response({}, false));

    await expect(fetchHealth(request)).rejects.toThrow("本地 API 暂时无法连接");
  });
});
