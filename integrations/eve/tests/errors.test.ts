import { describe, expect, it, vi } from "vitest";
import {
  errorMessage,
  isNotFoundError,
  isSetupError,
  logProviderError,
} from "../src/errors.js";

describe("errors", () => {
  it("classifies setup and not-found errors", () => {
    expect(isSetupError(new Error("Mem0 API key cannot be empty"))).toBe(true);
    expect(isSetupError(Object.assign(new Error("denied"), { name: "AuthenticationError" }))).toBe(
      true,
    );
    expect(isSetupError(new Error("mem0 down"))).toBe(false);
    expect(isNotFoundError(new Error("Memory not found"))).toBe(true);
    expect(isNotFoundError(new Error("HTTP 404"))).toBe(true);
    expect(errorMessage("x")).toBe("Unknown Mem0 error");
  });

  it("logs the original error object", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const failure = Object.assign(new Error("HTTP 401"), {
      name: "AuthenticationError",
    });
    try {
      logProviderError("recall failed", failure, { sessionId: "sess_1" });
      expect(error).toHaveBeenCalledWith("[@mem0/eve] recall failed", {
        error: failure,
        name: "AuthenticationError",
        message: "HTTP 401",
        sessionId: "sess_1",
      });
    } finally {
      error.mockRestore();
    }
  });
});
