import { useQuery } from "@tanstack/react-query";

import { SecretsService } from "#/api/secrets-service";
import { useIsAuthed } from "#/hooks/query/use-is-authed";

import { useConfig } from "./use-config";

export const useGetSecrets = () => {
  const { data: config } = useConfig();
  const { data: isAuthed } = useIsAuthed();

  const isOss = config?.app_mode === "oss";

  return useQuery({
    queryKey: ["secrets"],
    queryFn: SecretsService.getSecrets,
    enabled: isOss || isAuthed, // Enable regardless of providers
  });
};
