import React from "react";
import { useTranslation } from "react-i18next";

import { useAuditLog } from "#/hooks/query/use-audit-log";
import { useCurrentOrgId } from "#/hooks/use-current-org-id";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { AuditLogTable } from "#/components/features/admin/audit-log-table";
import type { AuditLogParams } from "#/api/admin-service/admin.types";

export default function AdminAuditPage() {
  const { t } = useTranslation();
  const orgId = useCurrentOrgId();

  const [params, setParams] = React.useState<AuditLogParams>({
    limit: 25,
    offset: 0,
  });
  const [actionFilter, setActionFilter] = React.useState("");
  const [autoRefresh, setAutoRefresh] = React.useState(false);

  const queryParams: AuditLogParams = {
    ...params,
    ...(actionFilter && { action: actionFilter }),
  };

  const { data: auditData, isLoading } = useAuditLog(orgId, queryParams);

  // Auto-refresh: refetch every 30 seconds when enabled
  React.useEffect(() => {
    if (!autoRefresh) return undefined;
    const interval = setInterval(() => {
      // TanStack Query will auto-refetch due to staleTime=30s
    }, 30_000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  // TODO(task-32): The backend audit endpoint should return
  // { items, total, limit, offset }. Until Task 32 is complete,
  // we fall back to the items array and estimate total.
  const items = auditData?.items ?? [];
  const total = auditData?.total ?? items.length;

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
          {t("ADMIN$AUDIT_TITLE", "Audit Log")}
        </h3>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
            className="rounded"
          />
          {t("ADMIN$AUTO_REFRESH", "Auto-refresh")}
        </label>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="action-filter" className="text-xs text-tertiary">
            {t("ADMIN$FILTER_ACTION", "Action")}
          </label>
          <input
            id="action-filter"
            type="text"
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setParams((prev) => ({ ...prev, offset: 0 }));
            }}
            placeholder={t(
              "ADMIN$FILTER_ACTION_PLACEHOLDER",
              "Filter by action...",
            )}
            className="rounded border border-tertiary bg-base px-3 py-1.5 text-sm"
          />
        </div>
      </div>

      {items.length > 0 ? (
        <AuditLogTable
          items={items}
          total={total}
          limit={params.limit ?? 25}
          offset={params.offset ?? 0}
          onPageChange={(offset) => setParams((prev) => ({ ...prev, offset }))}
          onLimitChange={(limit) =>
            setParams((prev) => ({ ...prev, limit, offset: 0 }))
          }
        />
      ) : (
        <p className="text-tertiary">
          {t("ADMIN$NO_AUDIT_LOGS", "No audit log entries.")}
        </p>
      )}
    </div>
  );
}
