import { useEffect } from "react";

import { useConfig } from "./query/use-config";

export const useBranding = () => {
  const { data: config } = useConfig();

  useEffect(() => {
    if (!config) return;

    // Validate favicon URL is HTTPS or relative path (prevent XSS via javascript: URLs)
    if (config.app_favicon_url) {
      const url = config.app_favicon_url;
      if (url.startsWith("https://") || url.startsWith("/")) {
        const link = document.querySelector(
          "link[rel~='icon']",
        ) as HTMLLinkElement;
        if (link) link.href = url;
      }
    }

    // Validate primary color matches CSS color pattern (prevent CSS injection)
    if (config.app_primary_color) {
      const colorPattern =
        /^(#[0-9a-fA-F]{3,8}|rgb\(\d{1,3},\s?\d{1,3},\s?\d{1,3}\)|hsl\(\d{1,3},\s?\d{1,3}%,\s?\d{1,3}%\))$/;
      if (colorPattern.test(config.app_primary_color)) {
        document.documentElement.style.setProperty(
          "--brand-primary",
          config.app_primary_color,
        );
      }
    }
  }, [config]);

  return {
    appName: config?.app_display_name ?? "OpenHands",
    logoUrl: config?.app_logo_url ?? null,
    primaryColor: config?.app_primary_color ?? null,
  };
};
