import { useQuery } from "@tanstack/react-query";

import AdminIntegrationService from "#/api/integration-service/admin-integration-service.api";

export const useAdminIntegrations = (orgId: string | null) =>
  useQuery({
    queryKey: ["admin-integrations", orgId],
    queryFn: () => AdminIntegrationService.getIntegrations(orgId!),
    enabled: !!orgId,
    staleTime: 1000 * 60 * 5,
  });
