import React from "react";
import { useTranslation } from "react-i18next";

import type { IntegrationConfig } from "#/api/integration-service/admin-integration-service.api";
import { BrandButton } from "#/components/features/settings/brand-button";
import { ModalBackdrop } from "#/components/shared/modals/modal-backdrop";

interface IntegrationConfigModalProps {
  integrationType: string;
  initialConfig: IntegrationConfig | null;
  onSave: (body: { enabled: boolean; config: Record<string, unknown> }) => void;
  onClose: () => void;
  isPending: boolean;
}

export function IntegrationConfigModal({
  integrationType,
  initialConfig,
  onSave,
  onClose,
  isPending,
}: IntegrationConfigModalProps) {
  const { t } = useTranslation();
  const [enabled, setEnabled] = React.useState(initialConfig?.enabled ?? false);
  const [configJson, setConfigJson] = React.useState(
    initialConfig?.config
      ? JSON.stringify(initialConfig.config, null, 2)
      : "{}",
  );
  const [jsonError, setJsonError] = React.useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const parsed = JSON.parse(configJson) as Record<string, unknown>;
      setJsonError(null);
      onSave({ enabled, config: parsed });
    } catch {
      setJsonError(t("ADMIN$INVALID_JSON", "Invalid JSON configuration"));
    }
  };

  return (
    <ModalBackdrop onClose={onClose}>
      <form
        onSubmit={handleSubmit}
        className="bg-base-secondary p-6 rounded-xl flex flex-col gap-4 border border-tertiary min-w-[420px] max-w-lg"
      >
        <h3 className="text-lg font-semibold capitalize">
          {t("ADMIN$CONFIGURE_INTEGRATION", "Configure {{type}}", {
            type: integrationType,
          })}
        </h3>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="rounded"
          />
          {t("ADMIN$ENABLED", "Enabled")}
        </label>
        <div className="flex flex-col gap-2">
          <label htmlFor="config-json" className="text-sm text-tertiary">
            {t("ADMIN$CONFIG_JSON", "Configuration (JSON)")}
          </label>
          <textarea
            id="config-json"
            value={configJson}
            onChange={(e) => {
              setConfigJson(e.target.value);
              setJsonError(null);
            }}
            rows={8}
            className="rounded border border-tertiary bg-base px-3 py-2 text-sm font-mono"
          />
          {jsonError && <p className="text-xs text-red-500">{jsonError}</p>}
        </div>
        <div className="flex gap-2 justify-end">
          <BrandButton
            type="button"
            variant="secondary"
            onClick={onClose}
            isDisabled={isPending}
          >
            {t("BUTTON$CANCEL", "Cancel")}
          </BrandButton>
          <BrandButton type="submit" variant="primary" isDisabled={isPending}>
            {isPending
              ? t("ADMIN$SAVING", "Saving...")
              : t("BUTTON$SAVE", "Save")}
          </BrandButton>
        </div>
      </form>
    </ModalBackdrop>
  );
}
