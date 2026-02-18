import { useConfig } from "#/hooks/query/use-config";
import {
  SAAS_NAV_ITEMS,
  OSS_NAV_ITEMS,
  APOLLOSAI_NAV_ITEMS,
} from "#/constants/settings-nav";

export function useSettingsNavItems() {
  const { data: config } = useConfig();

  const shouldHideLlmSettings = !!config?.feature_flags?.hide_llm_settings;
  const isSaasMode = config?.app_mode === "saas";
  const isBillingEnabled = !!config?.feature_flags?.enable_billing;

  // ApollosAI SaaS mode: saas without billing (no Stripe)
  const isApollosAI = isSaasMode && !isBillingEnabled;

  let items;
  if (isApollosAI) {
    items = APOLLOSAI_NAV_ITEMS;
  } else if (isSaasMode) {
    items = SAAS_NAV_ITEMS;
  } else {
    items = OSS_NAV_ITEMS;
  }

  return shouldHideLlmSettings
    ? items.filter((item) => item.to !== "/settings")
    : items;
}
