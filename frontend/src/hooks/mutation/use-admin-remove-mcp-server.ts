import { useMutation, useQueryClient } from "@tanstack/react-query";

import MCPAdminService from "#/api/mcp-admin-service/mcp-admin-service.api";

export const useAdminRemoveMCPServer = (orgId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (serverId: string) =>
      MCPAdminService.removeMCPServer(orgId, serverId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["admin-mcp-servers", orgId],
      });
    },
  });
};
