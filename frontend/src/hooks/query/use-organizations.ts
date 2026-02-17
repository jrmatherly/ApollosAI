import { useQuery } from "@tanstack/react-query";
import OrgService from "#/api/org-service/org-service.api";
import { useIsAuthed } from "./use-is-authed";

export const useOrganizations = () => {
  const { data: isAuthed } = useIsAuthed();

  return useQuery({
    queryKey: ["organizations"],
    queryFn: () => OrgService.getOrganizations(),
    enabled: !!isAuthed,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};
