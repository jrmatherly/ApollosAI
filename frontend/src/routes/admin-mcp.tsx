import React from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";

import { useAdminMCPServers } from "#/hooks/query/use-admin-mcp-servers";
import { useAdminAddMCPServer } from "#/hooks/mutation/use-admin-add-mcp-server";
import { useAdminRemoveMCPServer } from "#/hooks/mutation/use-admin-remove-mcp-server";
import { useCurrentOrgId } from "#/hooks/use-current-org-id";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { BrandButton } from "#/components/features/settings/brand-button";
import { MCPServerCard } from "#/components/features/admin/mcp-server-card";
import { AddMCPServerModal } from "#/components/features/admin/add-mcp-server-modal";
import MCPAdminService from "#/api/mcp-admin-service/mcp-admin-service.api";

export default function AdminMCPPage() {
  const { t } = useTranslation();
  const orgId = useCurrentOrgId();
  const queryClient = useQueryClient();
  const { data: servers, isLoading } = useAdminMCPServers(orgId);
  const addServer = useAdminAddMCPServer(orgId ?? "");
  const removeServer = useAdminRemoveMCPServer(orgId ?? "");

  const [showAddModal, setShowAddModal] = React.useState(false);
  const [isToggling, setIsToggling] = React.useState(false);

  const handleToggle = async (serverId: string, enabled: boolean) => {
    if (!orgId) return;
    setIsToggling(true);
    try {
      await MCPAdminService.updateMCPServer(orgId, serverId, { enabled });
      queryClient.invalidateQueries({
        queryKey: ["admin-mcp-servers", orgId],
      });
    } finally {
      setIsToggling(false);
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
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">
          {t("ADMIN$MCP_TITLE", "MCP Servers")}
        </h3>
        <BrandButton
          type="button"
          variant="primary"
          onClick={() => setShowAddModal(true)}
        >
          {t("ADMIN$ADD_MCP_SERVER", "Add MCP Server")}
        </BrandButton>
      </div>
      {servers && servers.length > 0 ? (
        <div className="rounded-lg border border-tertiary">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-tertiary text-left text-tertiary">
                <th className="px-4 py-3 font-medium">
                  {t("ADMIN$MCP_NAME", "Name")}
                </th>
                <th className="px-4 py-3 font-medium">
                  {t("ADMIN$MCP_TYPE", "Type")}
                </th>
                <th className="px-4 py-3 font-medium">
                  {t("ADMIN$MCP_STATUS", "Status")}
                </th>
                <th className="px-4 py-3 font-medium w-40" />
              </tr>
            </thead>
            <tbody>
              {servers.map((server) => (
                <MCPServerCard
                  key={server.id}
                  server={server}
                  onToggle={handleToggle}
                  onDelete={(serverId) => removeServer.mutate(serverId)}
                  isUpdating={
                    isToggling || removeServer.isPending || addServer.isPending
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-tertiary">
          {t("ADMIN$NO_MCP_SERVERS", "No MCP servers configured.")}
        </p>
      )}
      {showAddModal && (
        <AddMCPServerModal
          onSubmit={(body) => {
            addServer.mutate(body, {
              onSuccess: () => setShowAddModal(false),
            });
          }}
          onClose={() => setShowAddModal(false)}
          isPending={addServer.isPending}
        />
      )}
    </div>
  );
}
