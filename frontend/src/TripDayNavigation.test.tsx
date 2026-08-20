import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TripDayNavigation } from "./TripDayNavigation";

const days = [
  { local_date: "2026-08-15" },
  { local_date: "2026-08-16" },
  { local_date: "2026-08-17" },
];

describe("TripDayNavigation", () => {
  it("wraps accessible day buttons and marks the current date with text and aria", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <TripDayNavigation
        days={days}
        activeDate="2026-08-15"
        onSelect={onSelect}
      />,
    );

    expect(
      screen.getByRole("navigation", { name: "行程日期导航" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: /第 1 天.*2026-08-15/ }),
    ).toHaveAttribute("aria-current", "date");
    await user.click(
      screen.getByRole("button", { name: /第 3 天.*2026-08-17/ }),
    );
    expect(onSelect).toHaveBeenCalledWith("2026-08-17");
  });
});
