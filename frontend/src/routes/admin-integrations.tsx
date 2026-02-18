import React from "react";
import { useTranslation } from "react-i18next";

import { useAdminIntegrations } from "#/hooks/query/use-admin-integrations";
import { useSaveIntegrationConfig } from "#/hooks/mutation/use-save-integration-config";
import { useCurrentOrgId } from "#/hooks/use-current-org-id";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { IntegrationCard } from "#/components/features/admin/integration-card";
import { IntegrationConfigModal } from "#/components/features/admin/integration-config-modal";
import type { IntegrationConfig } from "#/api/integration-service/admin-integration-service.api";
import AdminIntegrationService from "#/api/integration-service/admin-integration-service.api";

export default function AdminIntegrationsPage() {
  const { t } = useTranslation();
  const orgId = useCurrentOrgId();
  const { data: integrations, isLoading } = useAdminIntegrations(orgId);
  const saveConfig = useSaveIntegrationConfig(orgId ?? "");

  const [configuringType, setConfiguringType] = React.useState<string | null>(
    null,
  );
  const [configData, setConfigData] = React.useState<IntegrationConfig | null>(
    null,
  );
  const [testingType, setTestingType] = React.useState<string | null>(null);
  const [testResult, setTestResult] = React.useState<{
    type: string;
    status: string;
  } | null>(null);

  const handleConfigure = async (type: string) => {
    if (!orgId) return;
    try {
      const config = await AdminIntegrationService.getIntegrationConfig(
        orgId,
        type,
      );
      setConfigData(config);
      setConfiguringType(type);
    } catch {
      setConfigData(null);
      setConfiguringType(type);
    }
  };

  const handleTest = async (type: string) => {
    if (!orgId) return;
    setTestingType(type);
    setTestResult(null);
    try {
      const result = await AdminIntegrationService.testIntegration(orgId, type);
      setTestResult({ type, status: result.status });
    } catch {
      setTestResult({ type, status: "error" });
    } finally {
      setTestingType(null);
    }
  };

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
      {testResult && (
        <div
          className={`rounded-lg px-4 py-2 text-sm ${
            testResult.status === "ok"
              ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
              : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
          }`}
        >
          {testResult.status === "ok"
            ? t("ADMIN$TEST_SUCCESS", "{{type}} connection successful", {
                type: testResult.type,
              })
            : t("ADMIN$TEST_FAILED", "{{type}} connection failed", {
                type: testResult.type,
              })}
        </div>
      )}
      {integrations && integrations.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {integrations.map((integration) => (
            <IntegrationCard
              key={integration.type}
              integration={integration}
              onConfigure={handleConfigure}
              onTest={handleTest}
              isTesting={testingType === integration.type}
            />
          ))}
        </div>
      ) : (
        <p className="text-tertiary">
          {t("ADMIN$NO_INTEGRATIONS", "No integrations configured.")}
        </p>
      )}
      {configuringType && (
        <IntegrationConfigModal
          integrationType={configuringType}
          initialConfig={configData}
          onSave={(body) => {
            saveConfig.mutate(
              { integrationType: configuringType, body },
              {
                onSuccess: () => {
                  setConfiguringType(null);
                  setConfigData(null);
                },
              },
            );
          }}
          onClose={() => {
            setConfiguringType(null);
            setConfigData(null);
          }}
          isPending={saveConfig.isPending}
        />
      )}
    </div>
  );
}
