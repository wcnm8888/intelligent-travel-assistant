import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { HealthPayload } from "./health";

const healthy: HealthPayload = {
  status: "ok",
  service: "intelligent-travel-assistant-api",
};

describe("App health diagnostics", () => {
  it("shows an explicit loading state and disables duplicate checks", () => {
    const neverResolves = vi.fn(
      () => new Promise<HealthPayload>(() => undefined),
    );

    render(<App checkHealth={neverResolves} />);

    expect(screen.getByRole("status")).toHaveTextContent("正在检查本地 API");
    expect(screen.getByRole("button", { name: /检查进行中/ })).toBeDisabled();
  });

  it("shows the connected service after a successful check", async () => {
    render(<App checkHealth={vi.fn().mockResolvedValue(healthy)} />);

    expect(await screen.findByText("连接正常")).toBeVisible();
    expect(screen.getByText("intelligent-travel-assistant-api")).toBeVisible();
    expect(screen.getByRole("button", { name: /重新检查/ })).toBeEnabled();
  });

  it("explains a failed connection and recovers when the user retries", async () => {
    const user = userEvent.setup();
    const checkHealth = vi
      .fn<() => Promise<HealthPayload>>()
      .mockRejectedValueOnce(new Error("sensitive transport detail"))
      .mockResolvedValueOnce(healthy);

    render(<App checkHealth={checkHealth} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "后端暂时无法连接",
    );
    expect(
      screen.queryByText("sensitive transport detail"),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /重新检查/ }));

    expect(await screen.findByText("连接正常")).toBeVisible();
    expect(checkHealth).toHaveBeenCalledTimes(2);
  });
});
