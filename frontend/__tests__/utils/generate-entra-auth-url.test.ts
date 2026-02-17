import { describe, it, expect } from "vitest";
import { generateEntraAuthUrl } from "#/utils/generate-entra-auth-url";

describe("generateEntraAuthUrl", () => {
  it("returns login URL with encoded returnTo", () => {
    const url = generateEntraAuthUrl("/conversations");
    expect(url).toBe("/api/auth/login?returnTo=%2Fconversations");
  });

  it("handles special characters in returnTo", () => {
    const url = generateEntraAuthUrl("/path?foo=bar&baz=1");
    expect(url).toContain("returnTo=");
    // & should be encoded
    expect(url).not.toContain("&baz=");
  });

  it("defaults to / when no returnTo provided", () => {
    const url = generateEntraAuthUrl();
    expect(url).toBe("/api/auth/login?returnTo=%2F");
  });

  it("encodes unicode characters", () => {
    const url = generateEntraAuthUrl("/path/café");
    expect(url).toContain("returnTo=");
    expect(decodeURIComponent(url.split("returnTo=")[1])).toBe("/path/café");
  });
});
