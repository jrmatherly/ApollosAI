import { useQuery } from "@tanstack/react-query";

import MCPAdminService from "#/api/mcp-admin-service/mcp-admin-service.api";

export const useAdminMCPServers = (orgId: string | null) =>
  useQuery({
    queryKey: ["admin-mcp-servers", orgId],
    queryFn: () => MCPAdminService.getMCPServers(orgId!),
    enabled: !!orgId,
    staleTime: 1000 * 60 * 5,
  });
