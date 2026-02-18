import { useMutation, useQueryClient } from "@tanstack/react-query";

import AdminService from "#/api/admin-service/admin-service.api";

export const useRemoveMember = (orgId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) => AdminService.removeMember(orgId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-members", orgId] });
    },
  });
};
