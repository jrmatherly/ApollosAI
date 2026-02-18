import { useTranslation } from "react-i18next";

import { useAdminIntegrations } from "#/hooks/query/use-admin-integrations";
import { useCurrentOrgId } from "#/hooks/use-current-org-id";
import { LoadingSpinner } from "#/components/shared/loading-spinner";

export default function AdminIntegrationsPage() {
  const { t } = useTranslation();
  const orgId = useCurrentOrgId();
  const { data: integrations, isLoading } = useAdminIntegrations(orgId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner size="large" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-lg font-semibold">
        {t("ADMIN$INTEGRATIONS_TITLE", "Integrations")}
      </h3>
      {integrations && integrations.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {integrations.map((integration) => (
            <div
              key={integration.type}
              className="rounded-lg border border-tertiary p-4 flex flex-col gap-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium capitalize">
                  {integration.type}
                </span>
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
            </div>
          ))}
        </div>
      ) : (
        <p className="text-tertiary">
          {t("ADMIN$NO_INTEGRATIONS", "No integrations configured.")}
        </p>
      )}
    </div>
  );
}
