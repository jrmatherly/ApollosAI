import { useTranslation } from "react-i18next";

import type { Integration } from "#/api/integration-service/admin-integration-service.api";
import { BrandButton } from "#/components/features/settings/brand-button";

interface IntegrationCardProps {
  integration: Integration;
  onConfigure: (type: string) => void;
  onTest: (type: string) => void;
  isTesting: boolean;
}

export function IntegrationCard({
  integration,
  onConfigure,
  onTest,
  isTesting,
}: IntegrationCardProps) {
  const { t } = useTranslation();

  return (
    <div className="rounded-lg border border-tertiary p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-medium capitalize">{integration.type}</span>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            integration.enabled
              ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
              : "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400"
          }`}
        >
          {integration.enabled
            ? t("ADMIN$STATUS_ENABLED", "Enabled")
            : t("ADMIN$STATUS_DISABLED", "Disabled")}
        </span>
      </div>
      <div className="flex gap-2">
        <BrandButton
          type="button"
          variant="secondary"
          onClick={() => onConfigure(integration.type)}
        >
          {t("ADMIN$CONFIGURE", "Configure")}
        </BrandButton>
        <BrandButton
          type="button"
          variant="secondary"
          onClick={() => onTest(integration.type)}
          isDisabled={!integration.enabled || isTesting}
        >
          {isTesting
            ? t("ADMIN$TESTING", "Testing...")
            : t("ADMIN$TEST_CONNECTION", "Test")}
        </BrandButton>
      </div>
    </div>
  );
}
