import { useTranslation } from "react-i18next";

import { useAuditLog } from "#/hooks/query/use-audit-log";
import { useCurrentOrgId } from "#/hooks/use-current-org-id";
import { LoadingSpinner } from "#/components/shared/loading-spinner";

export default function AdminAuditPage() {
  const { t } = useTranslation();
  const orgId = useCurrentOrgId();
  const { data: auditData, isLoading } = useAuditLog(orgId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner size="large" />
      </div>
    );
  }

  const items = auditData?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-lg font-semibold">
        {t("ADMIN$AUDIT_TITLE", "Audit Log")}
      </h3>
      {items.length > 0 ? (
        <div className="rounded-lg border border-tertiary overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-tertiary text-left text-tertiary">
                <th className="px-4 py-3 font-medium">
                  {t("ADMIN$AUDIT_TIMESTAMP", "Timestamp")}
                </th>
                <th className="px-4 py-3 font-medium">
                  {t("ADMIN$AUDIT_ACTION", "Action")}
                </th>
                <th className="px-4 py-3 font-medium">
                  {t("ADMIN$AUDIT_RESOURCE", "Resource")}
                </th>
                <th className="px-4 py-3 font-medium">
                  {t("ADMIN$AUDIT_ACTOR", "Actor")}
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((entry) => (
                <tr
                  key={entry.id}
                  className="border-b border-tertiary last:border-b-0"
                >
                  <td className="px-4 py-3 whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">{entry.action}</td>
                  <td className="px-4 py-3">
                    {entry.resource_type}:{entry.resource_id}
                  </td>
                  <td className="px-4 py-3 text-tertiary">
                    {entry.actor_id ?? "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-tertiary">
          {t("ADMIN$NO_AUDIT_LOGS", "No audit log entries.")}
        </p>
      )}
    </div>
  );
}
