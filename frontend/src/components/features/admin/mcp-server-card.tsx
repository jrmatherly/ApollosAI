import React from "react";
import { useTranslation } from "react-i18next";

import type { MCPServer } from "#/api/mcp-admin-service/mcp-admin-service.api";
import { BrandButton } from "#/components/features/settings/brand-button";
import { ConfirmationModal } from "#/components/shared/modals/confirmation-modal";

interface MCPServerCardProps {
  server: MCPServer;
  onToggle: (serverId: string, enabled: boolean) => void;
  onDelete: (serverId: string) => void;
  isUpdating: boolean;
}

export function MCPServerCard({
  server,
  onToggle,
  onDelete,
  isUpdating,
}: MCPServerCardProps) {
  const { t } = useTranslation();
  const [showDeleteConfirm, setShowDeleteConfirm] = React.useState(false);

  return (
    <>
      <tr className="border-b border-tertiary last:border-b-0">
        <td className="px-4 py-3">{server.name}</td>
        <td className="px-4 py-3 uppercase text-xs">{server.server_type}</td>
        <td className="px-4 py-3">
          <span
            className={`text-xs px-2 py-0.5 rounded-full ${
              server.enabled
                ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                : "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400"
            }`}
          >
            {server.enabled
              ? t("ADMIN$STATUS_ENABLED", "Enabled")
              : t("ADMIN$STATUS_DISABLED", "Disabled")}
          </span>
        </td>
        <td className="px-4 py-3 text-right">
          <div className="flex gap-2 justify-end">
            <BrandButton
              type="button"
              variant="secondary"
              onClick={() => onToggle(server.id, !server.enabled)}
              isDisabled={isUpdating}
            >
              {server.enabled
                ? t("ADMIN$DISABLE", "Disable")
                : t("ADMIN$ENABLE", "Enable")}
            </BrandButton>
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              disabled={isUpdating}
              className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50"
            >
              {t("ADMIN$DELETE", "Delete")}
            </button>
          </div>
        </td>
      </tr>
      {showDeleteConfirm && (
        <ConfirmationModal
          text={t(
            "ADMIN$CONFIRM_DELETE_MCP",
            'Are you sure you want to delete "{{name}}"?',
            { name: server.name },
          )}
          onConfirm={() => {
            onDelete(server.id);
            setShowDeleteConfirm(false);
          }}
          onCancel={() => setShowDeleteConfirm(false)}
        />
      )}
    </>
  );
}
