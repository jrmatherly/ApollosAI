import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  SAAS_NAV_ITEMS,
  OSS_NAV_ITEMS,
  APOLLOSAI_NAV_ITEMS,
} from "#/constants/settings-nav";
import OptionService from "#/api/option-service/option-service.api";
import { useSettingsNavItems } from "#/hooks/use-settings-nav-items";

const queryClient = new QueryClient();
const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

const mockConfig = (
  appMode: "saas" | "oss",
  featureFlags: Record<string, boolean> = {},
) => {
  vi.spyOn(OptionService, "getConfig").mockResolvedValue({
    app_mode: appMode,
    feature_flags: featureFlags,
  } as unknown as Awaited<ReturnType<typeof OptionService.getConfig>>);
};

describe("useSettingsNavItems", () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it("should return SAAS_NAV_ITEMS when app_mode is 'saas' with billing enabled", async () => {
    mockConfig("saas", { enable_billing: true });
    const { result } = renderHook(() => useSettingsNavItems(), { wrapper });

    await waitFor(() => {
      expect(result.current).toEqual(SAAS_NAV_ITEMS);
    });
  });

  it("should return APOLLOSAI_NAV_ITEMS when app_mode is 'saas' without billing", async () => {
    mockConfig("saas");
    const { result } = renderHook(() => useSettingsNavItems(), { wrapper });

    await waitFor(() => {
      expect(result.current).toEqual(APOLLOSAI_NAV_ITEMS);
    });
  });

  it("should return OSS_NAV_ITEMS when app_mode is 'oss'", async () => {
    mockConfig("oss");
    const { result } = renderHook(() => useSettingsNavItems(), { wrapper });

    await waitFor(() => {
      expect(result.current).toEqual(OSS_NAV_ITEMS);
    });
  });

  it("should filter out '/settings' item when hide_llm_settings feature flag is enabled", async () => {
    mockConfig("saas", { hide_llm_settings: true, enable_billing: true });
    const { result } = renderHook(() => useSettingsNavItems(), { wrapper });

    await waitFor(() => {
      expect(
        result.current.find((item) => item.to === "/settings"),
      ).toBeUndefined();
    });
  });
});
