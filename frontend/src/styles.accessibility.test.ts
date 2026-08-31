import { describe, expect, it } from "vitest";

import styles from "./styles.css?raw";

const parseHexColor = (value: string): [number, number, number] => {
  const match = value.match(/^#([0-9a-f]{6})$/i);
  if (!match) {
    throw new Error(`Expected a six-digit hex color, received ${value}`);
  }
  return [0, 2, 4].map((offset) =>
    Number.parseInt(match[1].slice(offset, offset + 2), 16),
  ) as [number, number, number];
};

const relativeLuminance = (value: string): number => {
  const [red, green, blue] = parseHexColor(value).map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
};

const contrastRatio = (foreground: string, background: string): number => {
  const foregroundLuminance = relativeLuminance(foreground);
  const backgroundLuminance = relativeLuminance(background);
  return (
    (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
    (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
  );
};

const cssVariable = (name: string): string => {
  const match = styles.match(new RegExp(`${name}:\\s*(#[0-9a-f]{6});`, "i"));
  if (!match) {
    throw new Error(`Missing CSS variable ${name}`);
  }
  return match[1];
};

describe("status text accessibility", () => {
  it("keeps partial and unknown-validity text at WCAG AA contrast", () => {
    const foreground = cssVariable("--status-partial");
    const backgrounds = [cssVariable("--paper"), cssVariable("--paper-raised")];

    for (const background of backgrounds) {
      expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(4.5);
    }

    expect(styles).toMatch(
      /\.result-stamp--partial\s*{\s*color:\s*var\(--status-partial\);\s*}/,
    );
    expect(styles).toMatch(
      /\.freshness--unknown_validity\s*{\s*color:\s*var\(--status-partial\);\s*}/,
    );
  });
});
