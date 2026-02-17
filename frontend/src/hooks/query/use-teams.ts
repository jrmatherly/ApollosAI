import { useQuery } from "@tanstack/react-query";
import OrgService from "#/api/org-service/org-service.api";
import { useIsAuthed } from "./use-is-authed";

export const useTeams = (orgId: string | null) => {
  const { data: isAuthed } = useIsAuthed();

  return useQuery({
    queryKey: ["teams", orgId],
    queryFn: () => OrgService.getTeams(orgId!),
    enabled: !!isAuthed && !!orgId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};
