import { describe, expect, it } from "vitest";
import { ApiError, normalizeError, unwrap } from "./api";

describe("api error handling", () => {
  it("rejects malformed envelopes", () => {
    expect(() => unwrap(undefined)).toThrow(ApiError);
    expect(() => unwrap({ ok: false })).toThrow(/unexpected format/);
    expect(() => unwrap({ ok: true })).toThrow(ApiError);
    expect(unwrap({ ok: true, data: { a: 1 } })).toEqual({ a: 1 });
  });
  it("maps server error bodies, timeouts and network failures", () => {
    const server = { isAxiosError: true, response: { status: 415, data: { error: { code: "unsupported_media_type", message: "Unsupported image type." } } } };
    expect(normalizeError(server).message).toBe("Unsupported image type.");
    expect(normalizeError(server).status).toBe(415);
    expect(normalizeError({ isAxiosError: true, code: "ECONNABORTED" }).code).toBe("timeout");
    expect(normalizeError({ isAxiosError: true }).code).toBe("network");
    expect(normalizeError({ isAxiosError: true, response: { status: 500, data: "<html>" } }).message).toMatch(/HTTP 500/);
    expect(normalizeError(new Error("secret stack")).message).not.toMatch(/secret/);
  });
});
