export interface HealthPayload {
  status: "ok";
  service: "intelligent-travel-assistant-api";
}

export class HealthCheckError extends Error {
  constructor() {
    super("本地 API 暂时无法连接");
    this.name = "HealthCheckError";
  }
}

function isHealthPayload(value: unknown): value is HealthPayload {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }

  const record = value as Record<string, unknown>;
  return (
    Object.keys(record).length === 2 &&
    record.status === "ok" &&
    record.service === "intelligent-travel-assistant-api"
  );
}

export async function fetchHealth(
  request: typeof fetch = fetch,
): Promise<HealthPayload> {
  try {
    const response = await request("/api/health", {
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new HealthCheckError();
    }

    const payload: unknown = await response.json();
    if (!isHealthPayload(payload)) {
      throw new HealthCheckError();
    }

    return payload;
  } catch {
    throw new HealthCheckError();
  }
}
