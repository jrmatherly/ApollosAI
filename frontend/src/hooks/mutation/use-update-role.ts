import { useMutation, useQueryClient } from "@tanstack/react-query";

import AdminService from "#/api/admin-service/admin-service.api";
import type { UpdateRoleBody } from "#/api/admin-service/admin.types";

export const useUpdateRole = (orgId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, body }: { userId: string; body: UpdateRoleBody }) =>
      AdminService.updateRole(orgId, userId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-members", orgId] });
    },
  });
};
