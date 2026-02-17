import { useQuery } from "@tanstack/react-query";

import AdminService from "#/api/admin-service/admin-service.api";

export const useOrgMembers = (orgId: string | null) =>
  useQuery({
    queryKey: ["org-members", orgId],
    queryFn: () => AdminService.getOrgMembers(orgId!),
    enabled: !!orgId,
    staleTime: 1000 * 60 * 5,
  });
