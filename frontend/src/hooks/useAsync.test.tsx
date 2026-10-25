// @vitest-environment jsdom
import { StrictMode, type ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useQuery } from "./useAsync";

// Regression: under StrictMode (enabled in main.tsx) the hook used to stay "dead" after the dev-only
// mount/unmount/mount cycle, so queries never delivered data and pages showed loading skeletons forever.
const wrapper = ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode>;

describe("useQuery", () => {
  it("delivers data under StrictMode", async () => {
    const { result } = renderHook(() => useQuery(async () => "hello", []), { wrapper });
    await waitFor(() => expect(result.current.data).toBe("hello"));
    expect(result.current.loading).toBe(false);
  });
  it("reports errors under StrictMode", async () => {
    const { result } = renderHook(() => useQuery(async () => { throw new Error("boom"); }, []), { wrapper });
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.loading).toBe(false);
  });
});
