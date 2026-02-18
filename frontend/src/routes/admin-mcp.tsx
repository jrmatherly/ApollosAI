import { useTranslation } from "react-i18next";

import { useAdminMCPServers } from "#/hooks/query/use-admin-mcp-servers";
import { useCurrentOrgId } from "#/hooks/use-current-org-id";
import { LoadingSpinner } from "#/components/shared/loading-spinner";

export default function AdminMCPPage() {
  const { t } = useTranslation();
  const orgId = useCurrentOrgId();
  const { data: servers, isLoading } = useAdminMCPServers(orgId);

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
              </tr>
            </thead>
            <tbody>
              {servers.map((server) => (
                <tr
                  key={server.id}
                  className="border-b border-tertiary last:border-b-0"
                >
                  <td className="px-4 py-3">{server.name}</td>
                  <td className="px-4 py-3 uppercase text-xs">
                    {server.server_type}
                  </td>
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-tertiary">
          {t("ADMIN$NO_MCP_SERVERS", "No MCP servers configured.")}
        </p>
      )}
    </div>
  );
}
