import { useQuery } from "@tanstack/react-query";

import BillingService from "#/api/billing-service/billing-service.api";
import { useIsOnTosPage } from "#/hooks/use-is-on-tos-page";

import { useConfig } from "./use-config";

export const useBalance = () => {
  const { data: config } = useConfig();
  const isOnTosPage = useIsOnTosPage();

  return useQuery({
    queryKey: ["user", "balance"],
    queryFn: BillingService.getBalance,
    enabled:
      !isOnTosPage &&
      config?.app_mode === "saas" &&
      config?.feature_flags?.enable_billing,
  });
};
