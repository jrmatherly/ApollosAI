import React from "react";
import { useTranslation } from "react-i18next";

import type { AuditLogEntry } from "#/api/admin-service/admin.types";
import { BrandButton } from "#/components/features/settings/brand-button";

interface AuditLogTableProps {
  items: AuditLogEntry[];
  total: number;
  limit: number;
  offset: number;
  onPageChange: (offset: number) => void;
  onLimitChange: (limit: number) => void;
}

const PAGE_SIZES = [10, 25, 50, 100];

export function AuditLogTable({
  items,
  total,
  limit,
  offset,
  onPageChange,
  onLimitChange,
}: AuditLogTableProps) {
  const { t } = useTranslation();
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-tertiary overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-tertiary text-left text-tertiary">
              <th className="px-4 py-3 font-medium">
                {t("ADMIN$AUDIT_TIMESTAMP", "Timestamp")}
              </th>
              <th className="px-4 py-3 font-medium">
                {t("ADMIN$AUDIT_ACTOR", "Actor")}
              </th>
              <th className="px-4 py-3 font-medium">
                {t("ADMIN$AUDIT_ACTION", "Action")}
              </th>
              <th className="px-4 py-3 font-medium">
                {t("ADMIN$AUDIT_RESOURCE", "Resource")}
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((entry) => (
              <React.Fragment key={entry.id}>
                <tr
                  className="border-b border-tertiary last:border-b-0 cursor-pointer hover:bg-base-secondary"
                  onClick={() =>
                    setExpandedId(expandedId === entry.id ? null : entry.id)
                  }
                >
                  <td className="px-4 py-3 whitespace-nowrap">
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-tertiary">
                    {entry.actor_id ?? "-"}
                  </td>
                  <td className="px-4 py-3">{entry.action}</td>
                  <td className="px-4 py-3">
                    {entry.resource_type}:{entry.resource_id}
                  </td>
                </tr>
                {expandedId === entry.id && (
                  <tr>
                    <td colSpan={4} className="px-4 py-3 bg-base-secondary">
                      <pre className="text-xs font-mono whitespace-pre-wrap overflow-x-auto">
                        {JSON.stringify(entry, null, 2)}
                      </pre>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          <span className="text-tertiary">
            {t("ADMIN$ROWS_PER_PAGE", "Rows per page:")}
          </span>
          <select
            value={limit}
            onChange={(e) => onLimitChange(Number(e.target.value))}
            className="rounded border border-tertiary bg-base px-2 py-1 text-sm"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-tertiary">
            {t("ADMIN$PAGE_INFO", "{{current}} of {{total}}", {
              current: currentPage,
              total: totalPages || 1,
            })}
          </span>
          <span className="text-tertiary">
            ({t("ADMIN$TOTAL_ITEMS", "{{count}} total", { count: total })})
          </span>
        </div>
        <div className="flex gap-1">
          <BrandButton
            type="button"
            variant="secondary"
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            isDisabled={offset === 0}
          >
            {t("ADMIN$PREV", "Prev")}
          </BrandButton>
          <BrandButton
            type="button"
            variant="secondary"
            onClick={() => onPageChange(offset + limit)}
            isDisabled={offset + limit >= total}
          >
            {t("ADMIN$NEXT", "Next")}
          </BrandButton>
        </div>
      </div>
    </div>
  );
}
