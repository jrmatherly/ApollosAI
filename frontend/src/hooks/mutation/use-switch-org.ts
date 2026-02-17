import { useMutation, useQueryClient } from "@tanstack/react-query";
import OrgService from "#/api/org-service/org-service.api";

export const useSwitchOrg = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (orgId: string) => OrgService.switchOrg(orgId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
    },
  });
};
