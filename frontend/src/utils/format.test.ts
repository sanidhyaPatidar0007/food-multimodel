import { describe, expect, it } from "vitest";
import { fmt, localDate, qty } from "./format";

describe("format helpers", () => {
  it("localDate uses local calendar fields, not UTC", () => {
    expect(localDate(new Date(2026, 0, 5, 23, 59))).toBe("2026-01-05");
    expect(localDate(new Date(2026, 11, 31, 0, 1))).toBe("2026-12-31");
  });
  it("fmt/qty handle nulls", () => {
    expect(fmt(null)).toBe("-");
    expect(qty(null, "g")).toBe("g");
    expect(qty(1.256, "tbsp")).toBe("1.26 tbsp");
  });
});
