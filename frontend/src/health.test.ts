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
      signal: expect.any(AbortSignal),
    });
  });

  it.each([
    { status: "degraded", service: "intelligent-travel-assistant-api" },
    { status: "ok" },
    { status: "ok", service: "wrong-api" },
    { status: "ok", service: 42 },
    { status: "ok", service: "intelligent-travel-assistant-api", extra: true },
  ])("rejects a malformed response without exposing it: %j", async (body) => {
    const request = vi.fn().mockResolvedValue(response(body));

    await expect(fetchHealth(request)).rejects.toBeInstanceOf(HealthCheckError);
  });

  it.each([
    vi.fn().mockRejectedValue(new Error("sensitive transport detail")),
    vi.fn().mockResolvedValue(response({}, false)),
    vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockRejectedValue(new Error("sensitive parse detail")),
    } as unknown as Response),
  ])(
    "maps transport, HTTP and parse failures to a safe local error",
    async (request) => {
      const result = fetchHealth(request);

      await expect(result).rejects.toEqual(new HealthCheckError());
    },
  );

  it("times out an unresponsive request and keeps the error recoverable", async () => {
    vi.useFakeTimers();
    const request = vi.fn(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        }),
    );

    const result = fetchHealth(request, 100);
    const assertion = expect(result).rejects.toEqual(new HealthCheckError());
    await vi.advanceTimersByTimeAsync(100);
    await assertion;
    vi.useRealTimers();
  });
});
