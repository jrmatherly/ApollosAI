import { useMutation, useQueryClient } from "@tanstack/react-query";

import AdminIntegrationService from "#/api/integration-service/admin-integration-service.api";
import type { SaveIntegrationConfigBody } from "#/api/integration-service/admin-integration-service.api";

export const useSaveIntegrationConfig = (orgId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      integrationType,
      body,
    }: {
      integrationType: string;
      body: SaveIntegrationConfigBody;
    }) =>
      AdminIntegrationService.saveIntegrationConfig(
        orgId,
        integrationType,
        body,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["admin-integrations", orgId],
      });
    },
  });
};
