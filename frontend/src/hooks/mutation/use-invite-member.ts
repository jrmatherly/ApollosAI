import { useMutation, useQueryClient } from "@tanstack/react-query";

import AdminService from "#/api/admin-service/admin-service.api";
import type { InviteMemberBody } from "#/api/admin-service/admin.types";

export const useInviteMember = (orgId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: InviteMemberBody) =>
      AdminService.inviteMember(orgId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-members", orgId] });
    },
  });
};
