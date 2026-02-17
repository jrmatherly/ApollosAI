import { useMutation, useQueryClient } from "@tanstack/react-query";

import MCPAdminService from "#/api/mcp-admin-service/mcp-admin-service.api";
import type { CreateMCPServerBody } from "#/api/mcp-admin-service/mcp-admin-service.api";

export const useAdminAddMCPServer = (orgId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: CreateMCPServerBody) =>
      MCPAdminService.addMCPServer(orgId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["admin-mcp-servers", orgId],
      });
    },
  });
};
