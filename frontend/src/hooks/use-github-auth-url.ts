import { WebClientConfig } from "#/api/option-service/option.types";

import { useAuthUrl } from "./use-auth-url";

interface UseGitHubAuthUrlConfig {
  appMode: WebClientConfig["app_mode"] | null;
  authUrl?: WebClientConfig["auth_url"];
}

export const useGitHubAuthUrl = (config: UseGitHubAuthUrlConfig) =>
  useAuthUrl({
    appMode: config.appMode,
    identityProvider: "github",
    authUrl: config.authUrl,
  });
