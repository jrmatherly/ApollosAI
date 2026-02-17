import { useMutation, useQueryClient } from "@tanstack/react-query";
import OrgService from "#/api/org-service/org-service.api";

export const useSwitchTeam = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (teamId: string) => OrgService.switchTeam(teamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });
};
